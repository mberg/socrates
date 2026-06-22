---
version: 0.1.0
last_modified: 2026-06-22
---
# Plan 4 — Tutor (Socratic guidance) (design)

**Design doc** · 2026-06-22

## 1. Purpose & scope

Give a child tiered, Socratic help on the problems they got wrong. From the graded **Results** screen, the child taps **"Get help"** on a wrong answer and opens an interactive chat scoped to that one problem. The tutor never reveals the answer until the child has worked through earlier hints and explicitly asks for more. Each turn can carry **trusted visual components** (number lines, fraction bars, etc.) — the model selects and parameterizes them, it never authors markup. This is **Plan 4** of the phased build (catalog = Plan 1, print + QR = Plan 2, grading = Plan 3 — all complete and merged to `main`).

**The slice this plan delivers** (spec §7, §7.1):

```
Results screen → "Get help" on a wrong ProblemResult
  → create GuidanceSession + opening Tier-1 nudge
  → child chats (typed or voice-to-text); each tutor turn = prose (Markdown+KaTeX) + optional visuals
  → "Still stuck — show me more" advances the tier (server-enforced floor)
  → correct answer only ever appears at Tier 3
  → every turn recorded (hint-load signal for a future mastery phase)
```

**In scope:**
- `GuidanceSession` + `TutorTurn` models + Alembic migration.
- A swappable `Tutor` interface (fake + Gemini), mirroring the existing `Vision` interface.
- A `VisualAction` discriminated union (the **Core 6** components) validated server-side with Pydantic.
- Guidance API: start session, post turn / advance tier, replay, resolve.
- Frontend: a `Tutor` chat drawer launched from `Results.tsx`; a `VisualRenderer` + six SVG components; Markdown+KaTeX rendering; **voice input** via the Web Speech API.

**Out of scope (later plans):** companion mode and mid-solving scan-help (the other two entry points); the handwriting-crop visual (needs per-problem bounding boxes captured during grading); Gemini Live real-time audio and tutor text-to-speech; and the mastery engine that *consumes* hint-load. Plan 4 records `GuidanceSession`/`TutorTurn` faithfully — nothing reads them yet.

## 2. Entry point — post-grade "Get help"

Of the spec's three tutor entry points, Plan 4 ships **post-grade only** — it has the richest grounding and reuses the existing Results UI. Each wrong `ProblemResult` already carries everything the tutor needs:

- `problem_id` → `Problem.prompt_text`, `Problem.correct_answer`, and the worksheet's `worked_example`.
- `read_answer` → the child's wrong/partial answer, so the tutor diagnoses the *specific* slip.

Companion mode (help from a sheet's question list, photo optional) and scan-help (mid-solving) are deferred to Plan 5. The `entry_point` field exists on `GuidanceSession` from day one so those drop in without a migration.

## 3. Backend architecture

### 3.1 Swappable `Tutor` interface

New package `backend/app/tutor/`, mirroring `grading/vision.py`'s swappable `Vision`:

```python
class Tutor(Protocol):
    async def respond(
        self, context: TutorContext, history: list[Turn], tier: int
    ) -> TutorReply: ...
```

- `GeminiTutor` implements it with the same `google-genai` SDK already wired for vision and ingestion, using **structured output** bound to the reply schema → Pydantic validation (the ingestion pattern). The single blocking SDK call is wrapped in `asyncio.to_thread(...)`, the same rule used by grading and ingest.
- `FakeTutor` (deterministic, no network) backs the tests and local dev.
- `TutorReply = { say: str, visuals: list[VisualAction] }`. The service validates each visual; an invalid/unknown one is **dropped** while `say` always survives (graceful degradation).
- Provider is selected the same way `get_vision()` selects vision, reading the existing Gemini settings in `config.py`.

### 3.2 `TutorContext` and structural tier enforcement

`TutorContext` is built server-side from the `ProblemResult` / `Problem` / `Worksheet` and always includes: problem prompt, worked example, grade level, child display name, and the child's wrong answer.

**Tier reveal is enforced structurally, not just by prompt.** This is the core safety property:

- The **literal `Problem.correct_answer` is injected into `TutorContext` only when Tier 3 is unlocked.** Below Tier 3 the model reasons from the worked example and method — it can diagnose the mistake ("you added when you needed to multiply") but **cannot reveal the final number because it does not have it.**
- The system prompt is the *soft* layer (stay on this problem, age-appropriate, don't give the answer early); context-withholding is the *hard* layer that makes a premature reveal structurally impossible.

The tier passed to `respond()` is the server's `max_tier_reached`, never a value the model can raise on its own.

### 3.3 Endpoints

Hung off the existing children/grading routers; whole-turn responses (no streaming — a turn is a structured payload, and partial-JSON rendering buys nothing at this scale; can be added later behind the same route):

| Method & path | Body | Effect |
| --- | --- | --- |
| `POST /children/{child_id}/problem-results/{result_id}/guidance` | — | Create (or return the open) `GuidanceSession` for that wrong problem **and** generate the opening **Tier-1 nudge**. |
| `POST /guidance/{session_id}/turns` | `{ text?, input_source, advance? }` | Append the child turn; if `advance`, bump tier `min(tier+1, 3)`; generate the tutor reply at the current tier; return the new tutor `TutorTurn`. The chat box and the "show me more" button both use this. |
| `GET /guidance/{session_id}` | — | Full replay (session + ordered turns). |
| `POST /guidance/{session_id}/resolve` | — | Mark `resolved = true`. |

## 4. Data model (spec §11)

Two new tables; no changes to existing tables. One Alembic migration.

**`GuidanceSession`** — one help event, mostly immutable:

```
id, child_id (fk), attempt_id (fk), problem_id (fk),
problem_result_id (fk),           # the specific wrong answer this addresses
entry_point: str = "post_grade",  # only value in Plan 4; field exists for Plan 5
max_tier_reached: int = 1,        # server-enforced floor; only this + resolved mutate
resolved: bool = False,
scan_attached: bool = False,      # always False in v1 (handwriting crop deferred)
created_at
```

**`TutorTurn`** — append-only, one row per chat turn:

```
id, session_id (fk, index),
role: str,                  # "child" | "tutor"
text: str,                  # Markdown+KaTeX prose (the tutor's `say`)
input_source: str | None,   # "typed" | "voice" for child turns; None for tutor
visuals: list[VisualAction] (JSON column),  # [] for child turns
tier: int,                  # tier active when this turn was produced
created_at
```

`visuals` is a JSON column holding the validated `VisualAction` list, the same JSON-column approach already used for extraction payloads. These rows are the **hint-load signal** (spec §8) for a future mastery phase — Plan 4 writes them; nothing reads them yet.

## 5. Visual component library — the Core 6

`VisualAction` is a discriminated union on `type`. Six components cover the dominant content across both grades (fractions, place value, decimals, multiplication/division, rounding, integers, PEMDAS). First-draft prop schemas (finalized in the plan):

| `type` | Props | Renders | Covers |
| --- | --- | --- | --- |
| `math` | `{ tex, display }` | KaTeX | expressions, fractions, equations — universal |
| `steps` | `{ title?, steps: [{ text, highlight? }] }` | ordered step list (text is md+KaTeX) | mirrors the sheet's worked example; any method |
| `number_line` | `{ min, max, ticks?, marks: [{ value, label?, color? }], jumps?: [{ from, to, label? }] }` | SVG line with marks & hop-arrows | place value, rounding, integers, decimals |
| `fraction_bar` | `{ bars: [{ denominator, shaded, label? }] }` | stacked partitioned bars (1+ to compare) | the whole fractions cluster |
| `place_value` | `{ value, columns? }` | base-10 blocks / place columns | regrouping, multi-digit, decimals |
| `mult_grid` | `{ rows, cols, partial? }` | array / area model, optional partial products | multiplication, division, arrays |

**Rendering contract:**
- Each maps to one SVG component in `frontend/src/components/visuals/`, dispatched by a single `VisualRenderer` that switches on `type`. Unknown `type` → render nothing (defensive; the backend already dropped invalid visuals).
- **SVG-only, no AI-generated images** (precise, instant, cheap — spec §7). Pure presentational components: props in, SVG out, independently testable.
- The model is handed exactly these six as its visual vocabulary in the structured-output schema. It selects and parameterizes; it never authors markup. This *is* the spec's safety guarantee (no raw HTML).

## 6. Frontend

**Entry:** a **"Get help"** button on each wrong-answer row in `Results.tsx`, opening `Tutor.tsx` as a drawer/modal over the results.

**`Tutor.tsx`** — the help session:
- On open, calls the guidance endpoint → renders the **Tier-1 nudge** (prose + any visuals).
- Message list: child + tutor bubbles. Each tutor bubble renders `text` via a Markdown+KaTeX renderer (`react-markdown` + `rehype-katex` + `katex`), then its `visuals` through `VisualRenderer`.
- **Input row:** text field + **mic button**. The mic uses a `useSpeechToText` hook over the Web Speech API: shows the interim transcript, drops the final text into the field (the child can edit before sending), and **hides itself gracefully** where the API is unsupported. Sends `input_source: "voice"` vs `"typed"`.
- **"Still stuck — show me more"** button → sends `advance: true`; disabled at Tier 3. The full answer only ever appears in a Tier-3 turn.
- A **"Got it"** affordance calls `resolve`.

**State:** session id + turns in component state; no global store. Reuses the typed API-client patterns in `api.ts`.

## 7. Testing & safety

**Backend** (provider behind the interface → `FakeTutor`, no network, like the grading fakes):
- **Tier floor:** `correct_answer` is *absent* from `TutorContext` below Tier 3 and *present* at Tier 3 — the structural guarantee, asserted directly.
- **Visual validation:** a malformed/unknown `VisualAction` is dropped while `say` is preserved.
- **Session lifecycle:** create → open-session reuse → append turns → `advance` caps at 3 → `resolve` → replay ordering.

**Frontend:**
- `VisualRenderer` renders each of the Core 6 from sample props (smoke).
- Tutor flow: open → reply renders (prose + visual) → send → "show me more" advances → Tier-3 reveal appears.
- Voice: mic hidden when the Web Speech API is absent; `input_source` set correctly.

**Safety** (kid-facing AI, spec §7.1): structured output = no raw HTML/injection; tier reveal enforced by context-withholding (hard) + system prompt (soft); the system prompt keeps the tutor on the current problem and age-appropriate.

## 8. Out of scope → Plan 5+

Companion mode; mid-solving scan-help; the handwriting-crop visual (needs per-problem bounding boxes from grading); Gemini Live audio + tutor TTS; and the mastery engine consuming hint-load. Plan 4 records the sessions faithfully so those layers have clean data to build on.
