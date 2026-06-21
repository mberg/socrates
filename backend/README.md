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
