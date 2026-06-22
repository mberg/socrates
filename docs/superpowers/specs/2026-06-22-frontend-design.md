---
version: 0.2.0
last_modified: 2026-06-22T20:15:08.000Z
---
# Frontend v1 — Print → Grade → Record (design)
<sub>`v0.2.0 · Last modified Jun 22, 2026 at 4:15 PM EDT`</sub>

**Design doc** · 2026-06-22
## 1. Purpose & scope
A real, iPad-usable web app for the core loop the backend already supports end to end: **print a worksheet, scan the completed sheet, grade it, and record the score.** This replaces the throwaway `/` test harness with a proper interface a parent and kids can actually use day to day.

Helping a child when they get stuck (the Socratic tutor) is the **explicit next phase** and is deliberately out of scope here — but the results screen is laid out so "Get help" drops in later without rework.

**In scope (v1):**

- Pick-a-profile home (kids as avatar tiles), with an optional per-kid PIN.
- Browse the catalog (topic → skill → worksheet) and print a sheet (QR/code, page-1 only).
- Scan a completed sheet with the iPad camera and grade it (synchronous).
- A recorded score history per kid, with a per-problem results detail that reveals the correct answer **only** on questions the child attempted and got wrong — never on blanks.

**Out of scope (later plans, backends not built):** the Socratic tutor / "Get help", mastery scoring, XP / badges / streaks, the recommender / "print next" queue, and the parent analytics dashboard.
## 2. Users, device, access
- **One responsive web app, iPad-first** (Safari on iPad over the home LAN, served from the same origin as the API). It must also work acceptably on a phone, but iPad is the design target.
- **No role split.** There is no separate "parent" vs "kid" application — anyone holding the iPad does the same flow (print / scan / scores) inside the selected kid's space. Catalog browsing in a kid's space defaults to that kid's grade.
- **Pick-a-profile, optional PIN.** The home screen shows each child as a large avatar tile plus an "Add kid" tile. Tapping a kid enters their space. If that kid has a PIN set, a 4-digit PIN prompt gates entry; if not, entry is immediate. PINs exist so the app can be shared with children beyond the family later without forcing friction now.
## 3. Architecture
- **React + Vite + TypeScript + Tailwind + shadcn/ui** (the stack named in the product spec §3).
- Lives in a new top-level `frontend/` directory (monorepo, alongside `backend/`).
- **Built to static assets and served by the existing FastAPI backend at** `/` (with `/api` and `/health` unchanged); the current test harness moves to `/dev`. One process to run on `claudius.local`; same origin, so no CORS and the iPad reaches it over the LAN exactly like the current harness.
- All data comes from the existing REST API under `/api`. The app holds no business logic the backend doesn't already own; it is a presentation layer over the catalog/attempt/grading endpoints.
- State: lightweight client state only (selected child, current attempt). Server data fetched per view; no heavy global store needed at this scale.
## 4. Screens & flow
### 4.1 Home — pick a profile
- Grid of large avatar tiles, one per child (name + grade + a simple avatar/color), plus an **Add kid** tile.
- Tap a kid → if `pin` is set, show a numeric PIN pad; on success (or if no PIN) enter the kid's space.
- **Add kid:** name, grade (3 or 5), optional 4-digit PIN. Creates a `Child`.
- A kid tile offers a small "edit" affordance to set/clear the PIN and fix name/grade.
### 4.2 Kid space
A simple tabbed/sectioned space scoped to one child, defaulting to their grade:

**Print**

- Browse: topic (catalog `topic`) → skill → worksheet. Grade is pre-filtered to the child's grade.
- **Print** on a worksheet creates an `Attempt` and opens the print PDF (page-1 only, QR + big code) for AirPrint. The new attempt appears under "Scan".

**Scan**

- Lists the child's **printed, not-yet-graded** attempts (status `printed`/`scanned`): worksheet title + code.
- Tap one → camera/upload (`<input type="file" accept="image/*" capture="environment">`) → POST the photo → a friendly "reading your answers…" state while grading runs synchronously (a few seconds) → results detail.
- A small **"tricky section"** toggle on this step sets `ai_fallback=true` for messier worksheets (forces the Gemini equivalence check on every mismatch).
- If the photo's printed code doesn't match the attempt (`identity_ok=false`), show a soft "is this the right sheet?" note — grading still proceeds.

**My scores**

- History of the child's **graded** attempts: worksheet title, score (e.g. `7/20`), date. Tap → results detail.
### 4.3 Results detail (privacy rules)
The answer key is revealed **only** on questions the child attempted and got wrong — never on blanks. Per problem, render by state:

- **Correct** (`is_correct=true`): ✓, celebrate. (No need to restate the answer — they got it.)
- **Wrong & attempted** (`is_correct=false`, `read_answer` non-null): ✗ with **what the child wrote** *and* **the correct answer**, so they can see the right result and self-correct. This is also where "Get help" will attach next phase.
- **Not attempted** (`read_answer` is null): shown as **"not attempted"** (not "wrong"), and **no answer revealed** — leaving questions blank must never surface the key.
- **Low-confidence read** (`needs_review=true`): a ⚐ "check this" marker.
- Header shows the recorded score and date.

{>>Applied c1: wrong-and-attempted now shows the correct answer; blanks still reveal nothing. This needs a backend change — the results payload must include the correct answer ONLY for attempted-wrong problems (see §5 item 4) — so the kid frontend cannot show a blank's answer even if asked. — claude<<}{id="c2" by="claude" at="2026-06-22T20:15:08.000Z" re="c1"}
## 5. Backend additions (small)
1. `Child.pin` — nullable string (store a hash, not plaintext), plus a verify path. Add `pin` (optional) to child create/update; a `POST /api/children/{id}/verify-pin` or equivalent returns ok/!ok. The PIN is a soft kid-profile guard, not real auth.
2. **Per-child graded-history summary** — `GET /api/children/{id}/scores` returning each graded attempt with `{attempt_id, worksheet_title, score_correct, score_total, graded_at}` so **My scores** is one call instead of N. (Detail still uses `GET /api/attempts/{id}/results`.)
3. **Serve the built frontend** from FastAPI as a static mount at `/`, keeping `/api` and `/health` unchanged; move the current test harness to `/dev`.
4. **Conditionally expose the correct answer** in the results payload (`GET /api/attempts/{id}/results` and the grade response): add `correct_answer` to each per-problem row, populated **only** when the problem was attempted and wrong (`read_answer` non-null **and** `is_correct=false`); `null` for correct and for not-attempted problems. This enforces the §4.3 rule server-side — a blank's answer is never sent to the client, so the UI can't reveal it. The print PDF still strips page 2 (unchanged).
## 6. Error / edge handling
- **No children yet:** home shows only "Add kid".
- **Grading failure (vision/network):** the attempt stays un-graded; show a retry; a new photo is just a new submission. "My scores" only lists attempts that actually graded (latest graded submission wins — already enforced server-side).
- **Wrong PIN:** re-prompt; no lockout in v1.
- **Offline / API down:** clear error state, no data fabrication.
## 7. Testing
- **Backend additions** follow the existing TDD pattern (pytest): `Child.pin` set/verify (hashed, wrong-PIN rejected, no-PIN child verifies open), and the scores-summary endpoint (graded attempts only, correct shape, ordering).
- **Backend (results payload):** `correct_answer` is present only for attempted-wrong rows and `null` for correct and not-attempted rows (the key never ships for blanks).
- **Frontend:** component/interaction tests for the core flows (Vitest + React Testing Library) — profile pick + PIN gate, browse→print calls create-attempt, scan upload renders results, and the results detail honors the privacy rules (shows the correct answer on attempted-wrong, never on not-attempted/blank reads). Keep tests behavior-focused, not snapshot-heavy.
- **Manual iPad pass:** print → solve → photograph on the iPad → grade → score recorded, end to end against the real catalog.
## 8. Deferred / explicit non-goals
- Socratic tutor / "Get help" on wrong answers (next phase).
- Mastery, XP, badges, streaks, daily stats.
- Recommender / "print next" queue; worksheet generator.
- Parent analytics dashboard.
- Real authentication / accounts (the per-kid PIN is a soft guard only).
- Offline support / PWA install.
