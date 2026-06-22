---
version: 0.1.0
last_modified: 2026-06-22
---
# Plan 3 — Grading (design)

**Design doc** · 2026-06-22

## 1. Purpose & scope

Turn a photo of a completed worksheet into scored results. A child snaps **one photo of the whole sheet**; the system identifies which printed sheet it is, reads every answer with a vision model, compares each to the stored answer key, and records an immutable per-problem result. This is **Plan 3** of the phased build (catalog = Plan 1, print + QR = Plan 2, both complete and merged to `main`).

**The slice this plan delivers** (spec §6):

```
upload photo → resolve Attempt → Vision reads all answers → align to known Problems
  → compare to answer key (code-normalized, Gemini fallback) → write Submission + ProblemResults
  → stamp Attempt.scanned_at / graded_at, status printed→scanned→graded
```

**In scope:** `Submission` + `ProblemResult` models + migration; a swappable `Vision` interface (fake + Gemini/Vertex); a synchronous grading service; answer comparison; the upload + results API; a human-readable Attempt id stamped on the print PDF.

**Out of scope (later plans):** mastery/XP, tutoring/guidance, handwriting crops for the tutor, the dashboard UI, the recommender, the worksheet generator. No new background-job, queue, or realtime infrastructure.

## 2. Execution model — synchronous, no queue

This is a **1–2 user system** (one parent, two children) grading a handful of sheets per day, one photo at a time. There is no throughput or contention problem to solve, so grading runs **synchronously inside the request**, exactly like ingestion already calls Gemini. The single blocking vision call is wrapped in `asyncio.to_thread(...)` so the event loop stays free (the same rule that fixed ingest concurrency).

**Explicitly rejected:** Redis/arq (a stateful service holding ~zero jobs) and Temporal (a durable workflow engine for long multi-step cross-service orchestration) — both are large infrastructure earning nothing at this scale. The grading service is written as a plain async function, so if asynchrony is ever wanted it can move behind FastAPI `BackgroundTasks` + a poll endpoint with no rewrite. It almost certainly won't be needed.

## 3. Data model

Two new tables, following the existing SQLModel + Alembic conventions in `app/models.py`. Both are **immutable append-only facts** (spec §11) — an Attempt may accumulate several Submissions (re-scans); the latest graded Submission is authoritative for the displayed score.

```
Submission                          # one uploaded photo against an Attempt; immutable
  id: str (uuid4 hex, pk)
  attempt_id: str (FK attempt.id, indexed)
  photo_r2_key: str                 # "submissions/<id>.<ext>"
  created_at: datetime (naive UTC via _utcnow)

ProblemResult                       # one per problem per submission; immutable
  id: str (uuid4 hex, pk)
  submission_id: str (FK submission.id, indexed)
  problem_id: str (FK problem.id, indexed)
  read_answer: str | None           # what the model read; None = blank/unreadable
  is_correct: bool
  confidence: float                 # vision read confidence, 0..1
  match_method: str                 # "exact" | "normalized" | "gemini_equiv"
  needs_review: bool                # true when the read was low-confidence
```

`Attempt` already carries `status` and `scanned_at` / `graded_at` (Plan 2) — no Attempt schema change. Status advances `printed → scanned → graded`.

Datetimes use the existing `_utcnow()` helper (naive UTC) to match Postgres `TIMESTAMP WITHOUT TIME ZONE` — the bug already learned in Plan 2.

## 4. Grading flow (one synchronous service call)

1. **Upload** — multipart photo → store bytes to R2 via `ObjectStore.put` at `submissions/<submission_id>.<ext>` → create `Submission`; set `Attempt.scanned_at`, status `scanned`.
2. **Resolve** — load the Attempt → its Worksheet → the ordered list of that worksheet's `Problem`s (number, prompt, correct_answer).
3. **Read** — `Vision.read(image_bytes, problems)` (in `asyncio.to_thread`) returns, per problem number, `{number, read_answer, confidence}` plus the **printed Attempt id it sees on the sheet**. The model is handed the problem numbers/prompts so it aligns its reading to the known layout instead of guessing. Blank/unreadable → `read_answer = None`.
4. **Identity cross-check** — normalize the printed id the model read (strip whitespace) and compare to the request's `attempt_id`. Mismatch → do not grade; surface a "wrong sheet?" error on the Submission. (See §6.)
5. **Compare per problem** — `grading/compare.py` normalized comparison first; **on a code mismatch** (and only when a non-blank answer was read), fall back to `Vision.judge_equivalence(read_answer, correct_answer)`. Record `is_correct` and `match_method` (`exact` / `normalized` / `gemini_equiv`). A code match is trusted as-is — re-judging an already-matched answer would waste a model call.
6. **Flag** — low-confidence reads set `needs_review = true` and are still scored (best-effort verdict; the parent can review/override later). Low confidence drives the review flag rather than a re-judge: the human-in-the-loop path, not a second model opinion, is what catches an uncertain read.
7. **Persist** — write all `ProblemResult`s, set `Attempt.graded_at`, status `graded`. Return the graded result (overall score + per-problem rows + a `needs_review` count).

**Per-problem fault isolation:** one unreadable/erroring problem never aborts the sheet — it becomes a blank/error result and grading continues (mirrors the ingest per-file isolation fix).

## 5. Vision interface + answer comparison

**`Vision` protocol** (new `app/grading/vision.py`), mirroring the existing `Extractor` pattern:

- `read(image: bytes, problems: list[...]) -> VisionRead` — returns per-problem reads + the printed id seen.
- `judge_equivalence(read_answer: str, correct_answer: str) -> bool` — cheap "are these the same answer?" check for the fallback.

Implementations: a **`FakeVision`** (deterministic, configured per test — drives all grading-service/API tests offline) and a **`GeminiVision`** reusing Plan 1's already-validated Vertex AI wiring (service-account creds, `gemini-3.x` family). No new model integration — same provider, new prompt.

**Comparison module** (`app/grading/compare.py`) — pure, deterministic, heavily unit-tested:

- trim + lowercase; strip surrounding units/words where present;
- canonicalize fractions (`3/6` → `1/2`), mixed numbers (`1 1/2` ↔ `3/2`), and decimals (`0.50` → `0.5`, trailing zeros);
- numeric equality when both parse as numbers.

Reuses the arithmetic-normalization ideas already in `app/ingest/validate.py` where applicable. Anything the code can't confidently equate (a non-blank read that fails the normalized compare) falls through to the Gemini equivalence check, so odd formats and word answers still grade correctly without making the common case nondeterministic. A blank/unreadable answer is recorded wrong (no fallback); a code match is trusted (no fallback).

## 6. Attempt resolution & the printed human-readable id

The QR on every printed sheet encodes exactly `Attempt.id` (Plan 2). For grading, the **client supplies `attempt_id`** with the upload (it always knows which Attempt is being scanned — from in-app navigation or by scanning the QR client-side). This needs no server-side QR-decode library.

For photo-as-source-of-truth robustness (spec §5, the "accuracy lever") **without** adding a native dependency (`pyzbar`/`opencv`), we add a **human-readable Attempt id** to the print:

- **Print change** (small tweak to Plan 2's `app/printing/print_pdf.py` + its test): stamp `Attempt.id` as plain monospace text directly beneath the QR. It equals the QR payload exactly — no new field, nothing to keep in sync.
- **Grading use:** the vision model reads that printed string off the photo (text OCR is reliable and free — it's already processing the image) and we cross-check it against the supplied `attempt_id`. Match → confident we're grading the right child's sheet; mismatch → flag rather than grade the wrong work.

Server-side QR *decoding* is intentionally **not** built — the human-readable cross-check delivers the same guarantee with zero dependencies. It remains a clean future add if ever wanted.

## 7. API

- `POST /children/{child_id}/attempts/{attempt_id}/submissions` — multipart photo upload; runs grading synchronously; returns the graded result. 404 if the attempt doesn't exist / doesn't belong to the child; 409/422-style error if the printed-id cross-check fails.
- `GET /attempts/{attempt_id}/results` — the latest submission's per-problem results + summary (score, `needs_review` count). 404 if never graded.

Follows the existing FastAPI router style in `app/api/` (catalog, children).

## 8. Error handling

- **Vision total failure** — `Submission` persists, `Attempt` stays `scanned` (not `graded`), error surfaced. Re-grade = a new Submission; no partial-graded state is left behind.
- **Identity mismatch** — Submission persists, not graded, "wrong sheet?" surfaced.
- **Per-problem errors** — isolated to that problem's result; the sheet still grades.
- **R2 ordering** — store the photo before creating the Submission row so a committed Submission always has its bytes (avoids the orphan-object asymmetry noted as a Plan 1 deferred item).

## 9. Testing (TDD throughout)

- **compare.py** — pure unit tests: integers, decimals/trailing zeros, fractions/mixed numbers, units, whitespace/case, blanks, non-equal pairs.
- **grading service** — with `FakeVision`: all-correct, some-wrong, low-confidence → `needs_review`, blank/unreadable problem, identity mismatch, per-problem fault isolation.
- **API** — upload → grade → results happy path; re-scan creates a second Submission and the latest wins; 404/identity-mismatch paths; results endpoint shape.
- **print** — the new human-readable id appears in the print PDF (extend the existing `test_print_pdf.py`).
- **migration** — autogenerated, then verified applying cleanly on real Postgres 16 (the Plan 1/2 procedure).
- **E2E** — one real Gemini/Vertex read of a single scanned sample sheet, verifying the per-problem verdicts (same Vertex-creds approach that validated Plan 1).

## 10. Deferred / explicit non-goals

- Mastery, XP, badges, streaks, daily stats (later plan).
- Tutoring / `GuidanceSession` / `TutorTurn` and handwriting crops.
- Parent-facing review/override UI (the `needs_review` flag is recorded now; the UI to act on it is later).
- The dashboard, recommender, and worksheet generator.
- Any queue/worker/realtime infrastructure.
- Server-side QR decoding (human-readable cross-check covers the need).
