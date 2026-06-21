---
version: 0.3.0
last_modified: 2026-06-21T04:01:44.000Z
---
# Socrates — Worksheet Tutor & Progress System
<sub>`v0.3.0 · Last modified Jun 21, 2026 at 12:01 AM EDT`</sub>

{>>Process note (claude): rewrite pass v0.3.0 — re-folded the deferred tutor-interaction detail (new §7.1 + TutorTurn in §11), added the section-selection menu (new §8.1), expanded ingestion (§13) with the filename-derived skill taxonomy, and fixed the §14 voice scope. Resolved comments c1/c3. Delete this note once read.<<}{id="c4" by="claude" at="2026-06-21T04:01:44.000Z"}

**Design doc** · 2026-06-20
## 1. Purpose
A web app for a parent to run a summer math program for two children (a 5th grader and a 3rd grader). The system recommends worksheets, prints them, grades the child's handwritten work from a photo, gives tiered Socratic guidance on mistakes, tracks per-skill mastery, and motivates the kids with points, levels, and a summer-long campaign. New worksheets can be generated on demand in the style of the source library.

**The core loop:**

```
recommend → print (worksheet only, QR-stamped) → kid solves on paper
  → snap photo (iPhone/iPad) → upload → Gemini reads answers
  → compare to stored answer key → score + per-problem results
  → update per-skill mastery → tiered guidance on wrong ones → award XP
  → recommend next  ↺        (generate a fresh sheet on demand any time)
```
## 2. Scope & constraints
- **Users:** one parent (operator) + two children with separate profiles. Each child has a grade level that scopes their catalog (grade 3 / grade 5; grade 4 reserved for later).
- **Duration:** a defined summer campaign, ~2 months (late June → late August 2026), with a start/end date and a goal per child.
- **Devices:** responsive web app, primary console on iPad; photos typically taken on an iPhone via the browser camera/file input. No native app.
- **Source material:** ~2,371 K5 Learning PDFs already downloaded (`/worksheets` grade 5, `/worksheet-g3` grade 3). **Every PDF is two pages: page 1 = blank worksheet, page 2 = answer key.** `pdftotext` extracts both cleanly. Each sheet includes a worked example at the top. K5 content is copyrighted — personal/family use only, never redistributed.
## 3. Stack
| Layer | Choice |
| --- | --- |
| Backend | FastAPI (Python) — also hosts PDF processing, QR, grading, generation |
| Frontend | React + Bun + Vite, shadcn/ui, Tailwind |
| DB  | Postgres (Railway) |
| ORM / migrations | SQLModel + Alembic + asyncpg |
| Storage | Cloudflare R2 (S3-compatible, via boto3/aioboto3) |
| Background jobs | arq (Redis) — grading & generation run off the request path |
| Realtime | WebSocket/SSE to stream grading progress to the UI |
| Vision (read scans) | Gemini, behind a swappable interface |
| Tutor / generator | Model-swappable (Gemini or other) |
| Hosting | Railway |

**Repo shape (monorepo):**

```
/backend    FastAPI, SQLModel, Alembic, pipelines, R2/Gemini clients
/frontend   Bun, React, shadcn, Tailwind
/worksheets, /worksheet-g3, /worksheets-g4   source PDFs (ingested → catalog + R2; git-ignored)
/docs/superpowers/specs/                       design docs
```
## 4. Components & pipelines
- **Frontend** — child picker, dashboard/mastery, worksheet browse + print, capture/upload, graded-results review, companion mode, tutor chat.
- **API (FastAPI)** — REST CRUD + a realtime channel so grading streams back ("reading… aligning… scoring…").
- **Worker (arq)** — runs the two slow pipelines.
- **Grading pipeline** (off request path): photo → QR identify → Gemini read → align to known problems → compare to answer key → ProblemResults → mastery update → XP.
- **Generation pipeline** (off request path): skill → learn pattern from existing sheets → generate problems + answers → validate answers in code → render printable PDF → catalog as `source = generated`.
- **External models** behind a small interface (`vision`, `tutor`, `generator`) so providers are swappable.
## 5. QR / print flow (the accuracy lever)
Every printed sheet carries a **QR code** encoding the `Attempt` id. This is the single biggest reliability lever: when a photo comes back, the QR tells us **exactly which worksheet, which child, and which attempt**, so Gemini's reading aligns to the right problems instead of guessing.

- **Print = worksheet page only.** Page 2 (answer key) is stripped before printing to save paper and keep answers from the child. The answer key stays internal for grading.
- Printing a sheet creates an `Attempt` (status `printed`) with its QR id and the R2 key of the stripped print PDF.
- The same worksheet printed twice = two `Attempt`s.
## 6. Grading pipeline
1. Child uploads a photo → stored in R2 → `Submission` created against the `Attempt` (resolved by QR).
2. Gemini reads the handwriting and returns per-problem answers.
3. Each read is aligned to a `Problem` (via QR-known layout) and compared to the stored correct answer.
4. `ProblemResult` per problem: what Gemini read, correct?, and **confidence**. **Low-confidence reads are flagged for the parent to review** rather than silently trusted.
5. Score + results stream to the UI; mastery and XP update.
## 7. Guidance / tutoring (the "Socrates" core)
Tiered, chat-style tutor that **never reveals the answer until Tier 3**:

1. **Tier 1 – Nudge:** a guiding question, no numbers given away.
2. **Tier 2 – Next step:** concrete, points at the specific slip.
3. **Tier 3 – Worked solution:** full steps, only on request or when clearly stuck.

**Three entry points, all logged identically:**

- **Scan → "help on Q7"** — mid-solving; because they scanned, the tutor reads their **partial work** and reacts to it.
- **Companion mode (in-app, no photo)** — once a sheet is *selected* (by QR scan **or** picked from the child's list), the app shows the **on-screen list of that sheet's questions** (rendered from parsed `Problem.prompt_text`). The kid taps any question → tutor opens. **Photo optional**: attach one and the tutor sees their work; skip it and it helps from the problem + method.
- **Post-grading "Get help"** — on each wrong answer; the tutor knows what they wrote *and* the correct answer, so it diagnoses the specific mistake.

**Grounding** (what the tutor is given): the exact problem text, the correct answer (from the parsed answer key), the **worked example** printed on the sheet (anchors hints to the method the sheet teaches), and the child's wrong/partial answer when available.

**Hint-load is a mastery signal:** a problem answered right only after heavy hinting is *not* mastered. Every help request is recorded (see `GuidanceSession`).

### 7.1 Tutor interaction (how the kid talks to the tutor)
A help session is an **interactive, generated chat thread scoped to one problem**, seeded with the grounding above (problem text, correct answer, worked example, and a crop of the child's handwriting when a scan is attached). Tier state is enforced **server-side** — the answer is not revealed until Tier 3 is unlocked. Every turn is logged.

**Input — modality-agnostic (v1: text + voice-to-text).** A "turn" is text regardless of how it was produced. v1 supports **typing** and **browser speech-to-text** (Web Speech API) so the child can *talk and get written responses* — important for the younger child, who types slowly. Future upgrade: **Gemini Live** real-time spoken tutoring (child talks, tutor talks back) and browser text-to-speech; the modality-agnostic turn model lets these drop in without reworking the tutor.

**Output — hybrid rich content.** Each tutor turn is a **structured payload**, not raw model HTML: a `say` field of **Markdown + KaTeX** prose, plus optional **`visual` actions** the model "calls" like tools and parameterizes, rendered by a **trusted, kid-friendly React component library** (number line, fraction bars, place-value blocks, multiplication grid, step-by-step list, KaTeX math). The model **cannot inject arbitrary HTML** — it only selects and parameterizes vetted components, keeping the kid-facing surface safe, consistent, and on-brand. For math, **SVG components are preferred over AI-generated images** (precise, instant, cheap; image models get spacing/quantities wrong). The tutor can also **show a crop of the child's own scanned handwriting** as a grounding visual ("here's the 54 you wrote").

**One provider:** the Gemini family powers vision (grading), tutor chat, and later live audio — a single integration, swappable behind the `vision` / `tutor` interfaces.

**Safety (kid-facing AI):** the system prompt keeps the tutor on the current problem, age-appropriate, and tier-respecting; structured output (no raw HTML) removes injection/rendering risk; tier unlock is server-enforced, not left to the model.
## 8. Mastery + recommendation engine
**Mastery is per child × skill**, an explainable score (no heavy ML), updated after each grade and guidance session from three signals:

- **Accuracy**, weighted toward **first-try correct**.
- **Hint-load** (from `GuidanceSession`s).
- **Recency / decay** — mastery fades if untouched, driving spaced review.

Skill states: **Not started → Learning → Practicing → Mastered.**

**Recommender** outputs a **"print next" queue (2–3 sheets)**, each with a plain-English reason:

- Prioritize weak/unmastered skills.
- Interleave spaced review of recently-learned skills.
- Stay in the child's grade, **don't repeat the exact worksheet** (pick another in the same skill or **generate** one), keep variety.

### 8.1 Navigation & section selection
The recommender is the **default** "what's next" surface, but it never locks the child in. Alongside it, a **browse menu mirrors the worksheet taxonomy** — grade → **topic (category)** → **skill (section)** — so a student or parent can **jump into any area and practice or print whatever they want**. This reuses the §11 `Skill → Worksheet` structure directly; no new model needed. The default journey still starts at the beginning of the grade and **auto-advances based on performance**, but free navigation is always available. Manual choice is **free navigation, not a focus-lock** — picking an area doesn't reconfigure the recommender, it just lets them work where they want. Incentives stay honest because **mastery-based diminishing XP (§9) applies however a skill is chosen**: self-selecting a mastered area earns little, so free choice can't be used to farm points. {>>Resolved c1/c3 (claude): grain = the worksheet's own categories/sections via a browse menu; recommender stays the default; free navigation, not a focus-lock; diminishing XP keeps it honest. Delete when read.<<}{id="c5" by="claude" at="2026-06-21T04:01:44.000Z"}
## 9. Gamification + summer campaign
- **Campaign:** per child, with start/end dates and a goal (e.g., "master 30 skills" / "complete 60 sheets"), shown as a progress bar with milestones.
- **Points (XP):** correct answers earn XP; bonuses for first-try-correct, completing a sheet, and **mastering a skill** (the big reward). **Mastered skills pay diminishing XP**, so easy sheets can't be farmed — points pull toward new/weak skills, same direction as the recommender. Asking for help never *costs* points (we don't punish help-seeking); it just forgoes the first-try bonus.
- **Levels:** XP thresholds → levels, per child.
- **Streaks:** consecutive days with a completed sheet.
- **Badges:** e.g. "Fraction Master," "10-Day Streak," "Comeback" (re-mastered a previously-failed skill).

**Two views:** kid view (level, XP, streak, badges, skills map, campaign bar); parent view (mastery heatmap, accuracy & hint-load trends, weekly struggles, recommended print queue).
## 10. Worksheet generator
When the library lacks a fresh sheet for a needed skill (or the recommender wants a non-repeat):

- Learn the **title, worked example, and problem patterns** from existing sheets of that skill.
- A model generates **new problems + correct answers** in that pattern.
- **Validate answers in code where possible** (math is checkable) so the answer key is trustworthy.
- Render to a **"good-enough" printable PDF** (title, example, numbered problems, QR); answer key stored internally. Enters the catalog as a `Worksheet` with `source = generated`, indistinguishable downstream.
## 11. Data model
**Principle: append-only facts, derived state.** Nothing that happened is ever overwritten; current-state tables are caches derived from the event stream. Every fact row stamps denormalized dimensions (`child_id, skill_id, topic, grade, source, occurred_at`) for slicing without heavy joins (a light star schema).

**Catalog (static library, built by ingestion):**

- **Skill** — teachable unit (grade, topic, slug). The grain for mastery and recommendations.
- **Worksheet** — one source sheet; belongs to a Skill. Fields: title, worked example, R2 key of source PDF, problem count, `source` (`k5` | `generated`).
- **Problem** — one numbered question: number, **prompt text**, **correct answer** (parsed from the two PDF pages). Powers grading *and* the companion's on-screen question list.

**Kids & activity:**

- **Child** — name, grade.
- **Attempt** — a printed instance of a worksheet for a child; carries the **QR id**; R2 key of stripped print PDF; `printed_at / scanned_at / graded_at`; status (`printed → scanned → graded`).
- **Submission** — one uploaded photo against an Attempt (R2 key, timestamp); immutable. An Attempt may have several (re-scan).
- **ProblemResult** — per problem on a graded submission: Gemini's read, correct?, confidence; immutable.
- **GuidanceSession** — a help event: child, worksheet, problem, timestamp, entry point (scan / in-app / post-grade), max tier reached, resolved?, scan-attached?; immutable.
- **TutorTurn** — append-only, one row per chat turn in a `GuidanceSession`: role (child / tutor), text, input source (typed / voice), any `visual` components emitted, and the tier active at that turn. Enables full session replay and fine-grained hint-load signal.

**Learning signals & analytics:**

- **MasteryState** — per child × skill: current score + counters (attempts, accuracy, hint-load, last-practiced). A **cache**; history lives in `MasteryEvent`.
- **MasteryEvent** — append-only; one row per skill state/score change. Enables mastery trend lines over the summer.
- **XpAward** — append-only ledger (amount, reason, skill, timestamp). Level / streak / total are **derived** from the ledger.
- **Badge** — timestamped earned-badge rows.
- **DailyStat** — rollup, one row per child per day (problems attempted, accuracy, first-try rate, hints used, XP earned, active?, skills-mastered count). Computed from facts (on write or nightly) for instant dashboard trends and streak/campaign math.

**Shape in one line:** `Skill → Worksheet → Problem` is the static library; `Child → Attempt → Submission → ProblemResult` is the activity; `GuidanceSession`, `MasteryEvent`, `XpAward`, `Badge`, `DailyStat` are the learning + analytics layers.
## 12. Analytics / dashboard (data now, UI later)
The data model above captures everything the per-child dashboard will need; the dashboard UI itself is **deferred**. With no further schema changes it can later show: accuracy & hint-load over time, mastery progression per skill, a topic heatmap, engagement/streak vs. the campaign, time-per-sheet, and "struggled most with" rankings — per child.
## 13. Ingestion (one-time, then on generation)
A one-time offline batch (an arq job / CLI command, parallelized over the ~2,400 sheets) populates `Skill / Worksheet / Problem`. Generated worksheets reuse the tail of this same pipeline.

**Skill taxonomy is derived from filenames — not hand-authored.** Stripping the grade prefix and the trailing variant letter collapses the library into skills: `grade-5-area-of-circles-a … -f.pdf` → Skill `area-of-circles`, with those files as interchangeable Worksheets. Grade 5 alone is ~1,128 PDFs → **~263 distinct skills**; the page-1 title ("Area of circles") is the human label; the folder is the topic/category. A few filenames break the `-[a-z]` convention (e.g. `…-cdf.pdf`, or no letter) — the normalizer tolerates these and **flags oddballs to quarantine** rather than mis-binning them.

**Per-PDF extraction — vision-primary, text as cross-check.** For each PDF: split page 1 (worksheet) / page 2 (answer key) with PyMuPDF; get `pdftotext` for both pages *and* render both pages to images; then one **Gemini call with a strict structured-output schema** → `{ title, instructions, worked_example, problems: [{ number, prompt, correct_answer }] }`, fed **both the page image and the extracted text** (the image handles fractions / geometry / long division / tables that text mangles; the text grounds it and curbs hallucination). Page 2 supplies the answers, page 1 the clean prompts. Vision-primary is chosen because the content is visual math across ~263 skills where regex-on-text is brittle, and because reading a clean printed sheet is far easier than the handwriting we already trust Gemini for — and it's a one-time batch, so model cost is a one-time concern.

**Validation gate before any insert.** Each extraction must pass: page-1/page-2 problem counts match, numbering is contiguous `1..N`, every problem has a non-empty answer, and — where the answer is arithmetic — it is **recomputed in code and confirmed**. Pass → insert. Fail or low-confidence → a **quarantine table for parent review**, never auto-trusted (bad parsed data would silently corrupt grading).

**Idempotent + auditable.** Hash each PDF (skip unchanged on re-runs); store the **raw model JSON + page text** beside the `Problem` rows so extractions can be re-derived and audited without re-calling the model. Generated sheets already carry structured, code-validated problems + answers, so they **skip extraction** and enter at the validation gate.
## 14. Out of scope (initial build)
- Dashboard UI (data captured now, built later).
- Native mobile app.
- Real-time spoken tutoring (Gemini Live) and tutor text-to-speech. (Voice *input* via browser speech-to-text **is** in scope for v1; the tutor replies in writing + visuals.)
- Grade 4 content (folder reserved).
- Multi-family / accounts beyond this household.
## 15. Open questions for planning
- Exact mastery scoring formula and state-transition thresholds.
- Recommender weighting (weak-skill priority vs. spaced-review cadence).
- XP/level curve and campaign goal defaults per grade.
- Extraction accuracy on the hardest visual layouts (geometry figures, multi-line word problems) and the volume of quarantined sheets needing manual review (see §13).
- Print pathway from the browser on iPad (direct print vs. download-then-print).
