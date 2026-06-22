# Socrates backend

## Setup

- Install poppler (`pdftotext`) and `uv`:
  ```bash
  # macOS
  brew install poppler uv
  # Linux (Debian/Ubuntu)
  sudo apt-get install poppler-utils
  ```

- Install Python dependencies:
  ```bash
  cd backend && uv sync
  ```

- Set environment variables in `.env`:
  - `GEMINI_API_KEY`: Developer API key for Google Generative AI (required for ingestion).
  - `DATABASE_URL`: PostgreSQL connection string (optional; defaults to SQLite for dry-runs).
  - `R2_BUCKET`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`: Cloudflare R2 credentials (optional; used for non-dry-run storage).

## Ingest the worksheet library

The ingestion pipeline discovers PDFs, extracts text and metadata, performs taxonomy parsing, and validates worksheets into a local SQLite database (dry-run) or PostgreSQL (production).

### Dry-run (no credentials required for discovery, PDF parse, taxonomy; Gemini extraction requires `GEMINI_API_KEY`)

Dry-run mode uses SQLite with in-memory storage and does not write to R2. Each PDF is processed but not persisted to external storage.

```bash
cd backend && GEMINI_API_KEY=$GEMINI_API_KEY uv run python -m app.cli ingest ../worksheets --dry-run
cd backend && GEMINI_API_KEY=$GEMINI_API_KEY uv run python -m app.cli ingest ../worksheet-g3 --dry-run
```

Expected output: summary of discovered PDFs, parsed sheets (status: inserted/skipped/quarantined), and final counts.

### Production run (requires PostgreSQL + R2 + Gemini credentials)

```bash
cd backend && DATABASE_URL=postgresql://... uv run alembic upgrade head
cd backend && uv run python -m app.cli ingest ../worksheets
```

## Print + QR

Create a child, create an attempt for a worksheet (generates a QR-stamped,
answer-key-stripped print PDF stored in R2), and download it to print:

    # with the API running (uv run uvicorn app.main:app), against the live DB + R2:
    curl -s -X POST localhost:8000/api/children -d '{"name":"Ada","grade":5}' -H 'content-type: application/json'
    # pick a worksheet id from GET /api/skills?grade=5 -> /skills/{id}/worksheets
    curl -s -X POST localhost:8000/api/children/CHILD_ID/attempts -d '{"worksheet_id":"WS_ID"}' -H 'content-type: application/json'
    curl -s localhost:8000/api/attempts/ATTEMPT_ID/print -o attempt.pdf  # 1-page, QR-stamped, no answer key

## Grading

### Pipeline overview

Grading is synchronous — no queue or background worker. When a photo is submitted:

1. **Upload** — the image is stored in R2 under the key `submissions/<submission_id>.<ext>` before any DB row is written, so a storage failure is always safe to retry.
2. **Vision read** — `GeminiVision.read` sends the image to Gemini (Vertex or API key) together with the worksheet's problem list. The model transcribes every handwritten answer and reads the human-readable attempt id stamped below the QR code (`printed_id`).
3. **Identity cross-check** — `printed_id` is compared to the attempt's own short id. A mismatch leaves the submission in `scanned` status with no results written, preventing a mis-filed photo from producing incorrect grades.
4. **Compare** — each transcribed answer is compared to the stored correct answer using `app.grading.compare`. Answers are first normalised (strip whitespace, lowercase, normalise unicode). If normalised strings differ, `GeminiVision.judge_equivalence` is called as a fallback so format variations ("1/2" vs "0.5") are handled correctly.
5. **Results** — a `Submission` row (status `graded`) and one `ProblemResult` row per problem are written in a single transaction. Problems answered with confidence below 0.8 set `needs_review = true` on the submission regardless of correctness.

### API endpoints

    # Submit a photo (multipart/form-data, field name "photo"):
    curl -s -X POST localhost:8000/api/children/CHILD_ID/attempts/ATTEMPT_ID/submissions \
      -F "photo=@/path/to/completed-sheet.jpg"
    # Returns: {"submission_id": "...", "status": "graded", "results": [...]}

    # Retrieve the latest graded results for an attempt:
    curl -s localhost:8000/api/attempts/ATTEMPT_ID/results
    # Returns: the most recent graded submission with per-problem results

### Vision interface

`app.grading.vision` defines a `Vision` protocol with two methods: `read` and `judge_equivalence`.

- **`FakeVision`** — used in tests; returns a fixed `VisionRead` without any network call.
- **`GeminiVision`** — production implementation. Instantiate with `use_vertex=True` (Vertex AI) or an `api_key` (developer API key).

### R2 key convention

Submission images are stored at `submissions/<submission_id>.<ext>` (e.g. `submissions/01J2AB3CD4EF5GH6IJ7KL8MN9P.jpg`). The submission id is generated before the upload so the key is stable and retries are idempotent.

### Human-readable attempt id cross-check

When an attempt is created, the attempt's full 32-char hex UUID (e.g. `3f9a1c4b8e2d7f0a...`) is stamped below the QR code on the print PDF. `GeminiVision.read` extracts this id from the photo (`printed_id`). If `printed_id` does not match the attempt's id, the submission is left in `scanned` status and no `ProblemResult` rows are written, so a photo submitted under the wrong attempt cannot silently produce wrong grades.

### Running the opt-in real-Vertex E2E test

The test in `tests/test_grading_e2e.py` is skipped automatically when `GEMINI_USE_VERTEX` is not set, so the normal suite stays offline. To run it against a real Vertex endpoint:

```bash
cd backend && GEMINI_USE_VERTEX=1 \
  GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa.json \
  GEMINI_VERTEX_PROJECT=<project> \
  GEMINI_VERTEX_LOCATION=<location> \
  GRADING_SAMPLE_IMAGE=/path/to/completed-sheet.jpg \
  uv run pytest tests/test_grading_e2e.py -v
```

## Tests

Run the full test suite:

```bash
cd backend && uv run pytest -v
```

## Database

Apply migrations (required for production runs):

```bash
cd backend && DATABASE_URL=postgresql://user:pass@localhost/socrates uv run alembic upgrade head
```

## Architecture

- `app/cli.py`: Command-line interface for ingestion.
- `app/ingest/pdf.py`: PDF text extraction and page rendering (using poppler + PyMuPDF).
- `app/ingest/taxonomy.py`: Filename-to-metadata parsing (grade, topic, skill_key, variant).
- `app/ingest/extractor.py`: Gemini-based problem extraction (multi-line JSON validation).
- `app/api/`: FastAPI endpoints for worksheet and skill queries.
- `app/models.py`: SQLAlchemy ORM models (Problem, Skill, Worksheet, etc.).
- `migrations/`: Alembic migration scripts for schema versioning.
