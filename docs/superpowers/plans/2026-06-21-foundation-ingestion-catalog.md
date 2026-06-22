# Foundation: Ingestion → Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Python backend and turn the ~2,400 downloaded K5 PDFs into a validated, browsable catalog (`Skill → Worksheet → Problem`) in Postgres.

**Architecture:** A FastAPI app with an async SQLModel data layer. A one-time ingestion pipeline derives the skill taxonomy from filenames, splits each PDF into worksheet/answer-key pages, extracts structured problems via a swappable vision `Extractor` interface (real Gemini impl + a fake for tests), runs every extraction through a validation gate before insert, and quarantines anything that fails. A small read API exposes the catalog. This is Plan 1 of the phased build (see the spec roadmap); grading, print/QR, tutoring, etc. are later plans.

**Tech Stack:** Python 3.12, FastAPI, SQLModel + Alembic + async SQLAlchemy (asyncpg in prod, aiosqlite in tests), Pydantic v2, PyMuPDF (page split + render), poppler `pdftotext` (page text), `google-genai` (Gemini, behind interface), boto3 (R2, behind interface), pytest + pytest-asyncio, `uv` for env/deps.

## Global Constraints

- **Python:** 3.12.
- **ORM:** SQLModel + Alembic + asyncpg; models use `Column(JSON)` (never native arrays) so the same models run on SQLite in tests and Postgres in prod.
- **Async sessions:** use SQLModel's `AsyncSession` (`from sqlmodel.ext.asyncio.session import AsyncSession`) everywhere a session is typed or created — it provides the `.exec()` used throughout. `async_sessionmaker` and `create_async_engine` still come from `sqlalchemy.ext.asyncio`.
- **Provider abstraction:** all Gemini and R2 access goes behind the `Extractor` / `ObjectStore` interfaces — never call the SDKs directly from pipeline or API code.
- **IDs:** primary keys are string UUID4 (`uuid4().hex`).
- **Grades in scope:** 3 and 5 (grade 4 folder reserved; ingestion must tolerate it being empty).
- **Source dirs:** `worksheets/` (grade 5), `worksheet-g3/` (grade 3) at repo root; both git-ignored.
- **Skill key rule:** filename stem with the `grade-N-` prefix removed and exactly one trailing `-<singleletter>` variant removed; multi-letter/no-letter suffixes are NOT stripped (treated as their own skill, `variant=None`).
- **Nothing untrusted enters the catalog:** an extraction is inserted only if it passes the validation gate (Task 7); failures go to `quarantined_extraction`.
- **System prereq:** poppler (`pdftotext`) on PATH; PyMuPDF wheel provides its own libs.

---

### Task 1: Project scaffold + health endpoint

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `app.main:create_app() -> FastAPI`; `app.config:Settings` (pydantic-settings) with `database_url: str`, `gemini_api_key: str = ""`, `r2_*` fields; module-level `settings = Settings()`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "socrates-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "sqlmodel>=0.0.22",
  "alembic>=1.13",
  "asyncpg>=0.29",
  "aiosqlite>=0.20",
  "pydantic-settings>=2.5",
  "pymupdf>=1.24",
  "google-genai>=0.3",
  "boto3>=1.35",
]

[dependency-groups]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "httpx>=0.27"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Write `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./socrates.db"
    gemini_api_key: str = ""
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "socrates"


settings = Settings()
```

- [ ] **Step 3: Write the failing test**

```python
# backend/tests/test_health.py
from httpx import ASGITransport, AsyncClient

from app.main import create_app


async def test_health_ok():
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 5: Write `app/main.py` and empty `conftest.py`**

```python
# backend/app/main.py
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Socrates")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

```python
# backend/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/app backend/tests
git commit -m "feat(backend): scaffold FastAPI app with health endpoint"
```

---

### Task 2: Catalog data models

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.config.settings`.
- Produces:
  - `app.db:engine`, `app.db:get_session() -> AsyncIterator[AsyncSession]`, `app.db:create_all() -> None` (test/bootstrap helper).
  - `app.models`: `Skill(id, grade:int, topic:str, skill_key:str unique, label:str)`, `Worksheet(id, skill_id, source:str, variant:str|None, title:str, worked_example:str|None, source_pdf_r2_key:str|None, problem_count:int, pdf_sha256:str unique)`, `Problem(id, worksheet_id, number:int, prompt:str, correct_answer:str, extraction_confidence:float|None)`, `QuarantinedExtraction(id, pdf_path:str, pdf_sha256:str, reason:str, raw_json:dict)`. All ids default to `uuid4().hex`.

- [ ] **Step 1: Write `app/db.py`**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings

engine = create_async_engine(settings.database_url, future=True)
_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_all() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as session:
        yield session
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_models.py
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Problem, Skill, Worksheet


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s


async def test_skill_worksheet_problem_roundtrip(session):
    skill = Skill(grade=5, topic="place-value-rounding", skill_key="place-value-5-digit", label="Build a 5-digit number")
    session.add(skill)
    await session.flush()
    ws = Worksheet(skill_id=skill.id, source="k5", variant="a", title="Build a 5-digit number",
                   worked_example="71,836 = 70,000 + ...", problem_count=1, pdf_sha256="abc123")
    session.add(ws)
    await session.flush()
    session.add(Problem(worksheet_id=ws.id, number=1, prompt="30,000 + 100 + 4", correct_answer="30,104"))
    await session.commit()

    rows = (await session.exec(select(Problem))).all()
    assert len(rows) == 1
    assert rows[0].correct_answer == "30,104"
    assert len(skill.id) == 32  # uuid4().hex
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 4: Write `app/models.py`**

```python
from uuid import uuid4

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy import JSON as SAJSON
from sqlmodel import Field, SQLModel


def _id() -> str:
    return uuid4().hex


class Skill(SQLModel, table=True):
    __tablename__ = "skill"
    __table_args__ = (UniqueConstraint("skill_key"),)
    id: str = Field(default_factory=_id, primary_key=True)
    grade: int
    topic: str
    skill_key: str = Field(index=True)
    label: str


class Worksheet(SQLModel, table=True):
    __tablename__ = "worksheet"
    __table_args__ = (UniqueConstraint("pdf_sha256"),)
    id: str = Field(default_factory=_id, primary_key=True)
    skill_id: str = Field(foreign_key="skill.id", index=True)
    source: str  # "k5" | "generated"
    variant: str | None = None
    title: str
    worked_example: str | None = None
    source_pdf_r2_key: str | None = None
    problem_count: int = 0
    pdf_sha256: str = Field(index=True)


class Problem(SQLModel, table=True):
    __tablename__ = "problem"
    id: str = Field(default_factory=_id, primary_key=True)
    worksheet_id: str = Field(foreign_key="worksheet.id", index=True)
    number: int
    prompt: str
    correct_answer: str
    extraction_confidence: float | None = None


class QuarantinedExtraction(SQLModel, table=True):
    __tablename__ = "quarantined_extraction"
    id: str = Field(default_factory=_id, primary_key=True)
    pdf_path: str
    pdf_sha256: str = Field(index=True)
    reason: str
    raw_json: dict = Field(default_factory=dict, sa_column=Column(SAJSON))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/db.py backend/app/models.py backend/tests/test_models.py
git commit -m "feat(backend): add catalog data models (Skill/Worksheet/Problem/Quarantine)"
```

---

### Task 3: Filename taxonomy parser (pure)

**Files:**
- Create: `backend/app/ingest/__init__.py`
- Create: `backend/app/ingest/taxonomy.py`
- Test: `backend/tests/test_taxonomy.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `app.ingest.taxonomy:Taxonomy` (dataclass: `grade:int, topic:str, skill_key:str, variant:str|None, regular:bool`) and `parse_filename(pdf_path: str) -> Taxonomy`. `topic` is the parent directory name; `regular` is False when no single-letter variant was stripped (flag for review).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_taxonomy.py
import pytest

from app.ingest.taxonomy import parse_filename


@pytest.mark.parametrize(
    "path, grade, topic, skill_key, variant, regular",
    [
        ("worksheets/place-value-rounding/grade-5-place-value-5-digit-a.pdf",
         5, "place-value-rounding", "place-value-5-digit", "a", True),
        ("worksheet-g3/telling-time/grade-3-calendar-reading-d.pdf",
         3, "telling-time", "calendar-reading", "d", True),
        ("worksheet-g3/telling-time/grade-3-calendar-months-as-numbers.pdf",
         3, "telling-time", "calendar-months-as-numbers", None, False),
        ("worksheet-g3/telling-time/grade-3-calendar-months-as-numbers-cdf.pdf",
         3, "telling-time", "calendar-months-as-numbers-cdf", None, False),
    ],
)
def test_parse_filename(path, grade, topic, skill_key, variant, regular):
    t = parse_filename(path)
    assert (t.grade, t.topic, t.skill_key, t.variant, t.regular) == (grade, topic, skill_key, variant, regular)


def test_parse_filename_rejects_non_grade():
    with pytest.raises(ValueError):
        parse_filename("worksheets/x/notes.pdf")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_taxonomy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingest.taxonomy'`

- [ ] **Step 3: Write `app/ingest/taxonomy.py`**

```python
import re
from dataclasses import dataclass
from pathlib import PurePath

_GRADE_RE = re.compile(r"^grade-(\d+)-(.+)$")
_VARIANT_RE = re.compile(r"^(.*)-([a-z])$")


@dataclass(frozen=True)
class Taxonomy:
    grade: int
    topic: str
    skill_key: str
    variant: str | None
    regular: bool


def parse_filename(pdf_path: str) -> Taxonomy:
    p = PurePath(pdf_path)
    topic = p.parent.name
    m = _GRADE_RE.match(p.stem)
    if not m:
        raise ValueError(f"not a grade-N worksheet: {pdf_path}")
    grade = int(m.group(1))
    rest = m.group(2)
    vm = _VARIANT_RE.match(rest)
    if vm:
        return Taxonomy(grade, topic, vm.group(1), vm.group(2), regular=True)
    return Taxonomy(grade, topic, rest, None, regular=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_taxonomy.py -v`
Expected: PASS (4 parametrized + 1)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest backend/tests/test_taxonomy.py
git commit -m "feat(ingest): filename->taxonomy parser with variant/regular detection"
```

---

### Task 4: PDF loader (split + render + text)

**Files:**
- Create: `backend/app/ingest/pdf.py`
- Test: `backend/tests/test_pdf.py`

**Interfaces:**
- Consumes: nothing (PyMuPDF + poppler).
- Produces: `app.ingest.pdf:PdfPages` (dataclass: `page_count:int, page1_png:bytes, page2_png:bytes|None, page1_text:str, page2_text:str|None`) and `load_pdf(path: str) -> PdfPages`. PNG is rendered at 150 DPI; text via `pdftotext -layout` per page.

- [ ] **Step 1: Write the failing test** (uses a real repo PDF)

```python
# backend/tests/test_pdf.py
from pathlib import Path

import pytest

from app.ingest.pdf import load_pdf

SAMPLE = "worksheets/place-value-rounding/grade-5-place-value-5-digit-a.pdf"


@pytest.mark.skipif(not Path(SAMPLE).exists(), reason="source PDFs not present")
def test_load_pdf_splits_and_reads():
    pages = load_pdf(SAMPLE)
    assert pages.page_count == 2
    assert pages.page1_png[:8] == b"\x89PNG\r\n\x1a\n"
    assert pages.page2_png is not None
    assert "Build a 5-digit number" in pages.page1_text
    # answer key page contains a filled answer the worksheet page does not
    assert "30,104" in pages.page2_text
    assert "30,104" not in pages.page1_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_pdf.py -v` (run from repo root so the relative path resolves: `uv run --project backend pytest backend/tests/test_pdf.py -v`)
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingest.pdf'`

- [ ] **Step 3: Write `app/ingest/pdf.py`**

```python
import subprocess
from dataclasses import dataclass

import fitz  # PyMuPDF

_DPI = 150


@dataclass(frozen=True)
class PdfPages:
    page_count: int
    page1_png: bytes
    page2_png: bytes | None
    page1_text: str
    page2_text: str | None


def _page_text(path: str, page_index: int) -> str:
    n = page_index + 1  # pdftotext is 1-based
    out = subprocess.run(
        ["pdftotext", "-layout", "-f", str(n), "-l", str(n), path, "-"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def _render_png(doc: "fitz.Document", page_index: int) -> bytes:
    pix = doc.load_page(page_index).get_pixmap(dpi=_DPI)
    return pix.tobytes("png")


def load_pdf(path: str) -> PdfPages:
    doc = fitz.open(path)
    try:
        count = doc.page_count
        return PdfPages(
            page_count=count,
            page1_png=_render_png(doc, 0),
            page2_png=_render_png(doc, 1) if count > 1 else None,
            page1_text=_page_text(path, 0),
            page2_text=_page_text(path, 1) if count > 1 else None,
        )
    finally:
        doc.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --project backend pytest backend/tests/test_pdf.py -v`
Expected: PASS (or SKIP if PDFs absent — then verify on a machine with the PDFs present)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/pdf.py backend/tests/test_pdf.py
git commit -m "feat(ingest): PDF loader (PyMuPDF split/render + pdftotext per page)"
```

---

### Task 5: Extractor interface + fake + Gemini impl

**Files:**
- Create: `backend/app/ingest/extractor.py`
- Create: `backend/app/ingest/gemini_extractor.py`
- Test: `backend/tests/test_extractor.py`

**Interfaces:**
- Consumes: `app.ingest.pdf.PdfPages`.
- Produces:
  - `ExtractedProblem(number:int, prompt:str, correct_answer:str, confidence:float|None)` and `Extraction(title:str, instructions:str|None, worked_example:str|None, problems:list[ExtractedProblem])` (Pydantic models).
  - `Extractor` Protocol: `def extract(self, pages: PdfPages) -> Extraction`.
  - `FakeExtractor(result: Extraction)` returning the canned result.
  - `app.ingest.gemini_extractor:GeminiExtractor(api_key)` implementing `Extractor` via `google-genai` structured output.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_extractor.py
from app.ingest.extractor import Extraction, ExtractedProblem, FakeExtractor
from app.ingest.pdf import PdfPages


def _pages():
    return PdfPages(2, b"\x89PNG", b"\x89PNG", "prompt text", "answer text")


def test_fake_extractor_returns_canned_result():
    canned = Extraction(
        title="Build a 5-digit number", instructions=None, worked_example="ex",
        problems=[ExtractedProblem(number=1, prompt="30,000 + 100 + 4", correct_answer="30,104", confidence=0.99)],
    )
    out = FakeExtractor(canned).extract(_pages())
    assert out.title == "Build a 5-digit number"
    assert out.problems[0].correct_answer == "30,104"


def test_extraction_rejects_empty_answer():
    import pydantic
    try:
        ExtractedProblem(number=1, prompt="x", correct_answer="", confidence=None)
    except pydantic.ValidationError as e:
        assert "correct_answer" in str(e)
    else:
        raise AssertionError("expected ValidationError for empty answer")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingest.extractor'`

- [ ] **Step 3: Write `app/ingest/extractor.py`**

```python
from typing import Protocol

from pydantic import BaseModel, field_validator

from app.ingest.pdf import PdfPages


class ExtractedProblem(BaseModel):
    number: int
    prompt: str
    correct_answer: str
    confidence: float | None = None

    @field_validator("correct_answer")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("correct_answer must be non-empty")
        return v


class Extraction(BaseModel):
    title: str
    instructions: str | None = None
    worked_example: str | None = None
    problems: list[ExtractedProblem]


class Extractor(Protocol):
    def extract(self, pages: PdfPages) -> Extraction: ...


class FakeExtractor:
    def __init__(self, result: Extraction) -> None:
        self._result = result

    def extract(self, pages: PdfPages) -> Extraction:
        return self._result
```

- [ ] **Step 4: Write `app/ingest/gemini_extractor.py`** (thin real impl; not unit-tested here — exercised in manual/integration runs)

```python
from google import genai

from app.ingest.extractor import Extraction
from app.ingest.pdf import PdfPages

_PROMPT = (
    "You are given two images: page 1 is a blank math worksheet, page 2 is its "
    "answer key, plus their extracted text. Return the worksheet's title, any "
    "instructions, the worked example, and every numbered problem with its prompt "
    "(from page 1) and correct answer (from page 2). Numbers must be contiguous "
    "starting at 1. Set confidence in [0,1] per problem."
)


class GeminiExtractor:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def extract(self, pages: PdfPages) -> Extraction:
        parts = [
            _PROMPT,
            f"PAGE 1 TEXT:\n{pages.page1_text}",
            f"PAGE 2 TEXT:\n{pages.page2_text or ''}",
            genai.types.Part.from_bytes(data=pages.page1_png, mime_type="image/png"),
        ]
        if pages.page2_png:
            parts.append(genai.types.Part.from_bytes(data=pages.page2_png, mime_type="image/png"))
        resp = self._client.models.generate_content(
            model=self._model,
            contents=parts,
            config={"response_mime_type": "application/json", "response_schema": Extraction},
        )
        return Extraction.model_validate_json(resp.text)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_extractor.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/ingest/extractor.py backend/app/ingest/gemini_extractor.py backend/tests/test_extractor.py
git commit -m "feat(ingest): Extractor interface, fake, and Gemini structured-output impl"
```

---

### Task 6: Object store interface (R2) + fake

**Files:**
- Create: `backend/app/storage.py`
- Test: `backend/tests/test_storage.py`

**Interfaces:**
- Consumes: `app.config.settings`.
- Produces: `ObjectStore` Protocol (`def put(self, key: str, data: bytes, content_type: str) -> str` returning the key); `InMemoryObjectStore` (test fake exposing `.objects: dict[str, bytes]`); `R2ObjectStore` (boto3 impl, not unit-tested).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_storage.py
from app.storage import InMemoryObjectStore


def test_in_memory_put_stores_bytes():
    store = InMemoryObjectStore()
    key = store.put("worksheets/x.pdf", b"%PDF-1.4", "application/pdf")
    assert key == "worksheets/x.pdf"
    assert store.objects["worksheets/x.pdf"] == b"%PDF-1.4"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.storage'`

- [ ] **Step 3: Write `app/storage.py`**

```python
from typing import Protocol

import boto3

from app.config import settings


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> str: ...


class InMemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self.objects[key] = data
        return key


class R2ObjectStore:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        )
        self._bucket = settings.r2_bucket

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return key
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/storage.py backend/tests/test_storage.py
git commit -m "feat(backend): ObjectStore interface with in-memory fake and R2 impl"
```

---

### Task 7: Validation gate (pure)

**Files:**
- Create: `backend/app/ingest/validate.py`
- Test: `backend/tests/test_validate.py`

**Interfaces:**
- Consumes: `app.ingest.extractor.Extraction`.
- Produces: `ValidationResult(ok:bool, reason:str|None, confidence:float)` and `validate(extraction: Extraction) -> ValidationResult`. Checks: ≥1 problem; numbering contiguous `1..N`; every answer non-empty (guaranteed by model, re-checked); for prompts that are a bare binary arithmetic expression, recompute and require a match. `confidence` = min problem confidence (default 1.0).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_validate.py
from app.ingest.extractor import Extraction, ExtractedProblem
from app.ingest.validate import validate


def _ex(problems):
    return Extraction(title="t", instructions=None, worked_example=None, problems=problems)


def test_valid_contiguous_passes():
    res = validate(_ex([
        ExtractedProblem(number=1, prompt="2 + 3", correct_answer="5"),
        ExtractedProblem(number=2, prompt="10 - 4", correct_answer="6"),
    ]))
    assert res.ok and res.reason is None


def test_non_contiguous_numbering_quarantined():
    res = validate(_ex([
        ExtractedProblem(number=1, prompt="x", correct_answer="a"),
        ExtractedProblem(number=3, prompt="y", correct_answer="b"),
    ]))
    assert not res.ok
    assert "contiguous" in res.reason


def test_wrong_arithmetic_quarantined():
    res = validate(_ex([ExtractedProblem(number=1, prompt="6 x 8", correct_answer="54")]))
    assert not res.ok
    assert "arithmetic" in res.reason


def test_empty_problem_list_quarantined():
    res = validate(_ex([]))
    assert not res.ok
    assert "no problems" in res.reason
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_validate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingest.validate'`

- [ ] **Step 3: Write `app/ingest/validate.py`**

```python
import re
from dataclasses import dataclass

from app.ingest.extractor import Extraction

_ARITH_RE = re.compile(r"^\s*([\d,]+)\s*([+\-x×*])\s*([\d,]+)\s*=?\s*$")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str | None
    confidence: float


def _as_int(s: str) -> int:
    return int(s.replace(",", ""))


def _check_arithmetic(prompt: str, answer: str) -> bool | None:
    m = _ARITH_RE.match(prompt)
    if not m:
        return None
    a, op, b = _as_int(m.group(1)), m.group(2), _as_int(m.group(3))
    expected = {"+": a + b, "-": a - b, "x": a * b, "×": a * b, "*": a * b}[op]
    try:
        return _as_int(answer) == expected
    except ValueError:
        return False


def validate(extraction: Extraction) -> ValidationResult:
    problems = extraction.problems
    if not problems:
        return ValidationResult(False, "no problems extracted", 0.0)
    numbers = [p.number for p in problems]
    if numbers != list(range(1, len(problems) + 1)):
        return ValidationResult(False, f"numbering not contiguous 1..N: {numbers}", 0.0)
    for p in problems:
        checked = _check_arithmetic(p.prompt, p.correct_answer)
        if checked is False:
            return ValidationResult(False, f"arithmetic mismatch on #{p.number}: {p.prompt}={p.correct_answer}", 0.0)
    confidence = min((p.confidence for p in problems if p.confidence is not None), default=1.0)
    return ValidationResult(True, None, confidence)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_validate.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/validate.py backend/tests/test_validate.py
git commit -m "feat(ingest): validation gate (contiguity + arithmetic recompute)"
```

---

### Task 8: Ingestion orchestrator (idempotent, persists or quarantines)

**Files:**
- Create: `backend/app/ingest/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `parse_filename`, `load_pdf` (injected as `loader`), `Extractor`, `validate`, `ObjectStore`, `AsyncSession`, models.
- Produces: `IngestOutcome(status:str, worksheet_id:str|None, reason:str|None)` (`status` ∈ `"inserted" | "skipped" | "quarantined"`) and `async ingest_pdf(path, *, session, extractor, store, loader=load_pdf) -> IngestOutcome`. Upserts `Skill` by `skill_key`; dedupes `Worksheet` by `pdf_sha256`; uploads source PDF to `store` under `worksheets/{sha}.pdf`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_orchestrator.py
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.ingest.extractor import Extraction, ExtractedProblem, FakeExtractor
from app.ingest.orchestrator import ingest_pdf
from app.ingest.pdf import PdfPages
from app.models import Problem, QuarantinedExtraction, Skill, Worksheet
from app.storage import InMemoryObjectStore


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        yield s


def _fake_loader(path: str) -> PdfPages:
    return PdfPages(2, b"\x89PNG", b"\x89PNG", "p1", "p2")


def _make_pdf(tmp_path, content=b"%PDF-1.4 dummy") -> str:
    d = tmp_path / "place-value-rounding"
    d.mkdir(exist_ok=True)
    p = d / "grade-5-place-value-5-digit-a.pdf"
    p.write_bytes(content)
    return str(p)


_GOOD = Extraction(title="Build a 5-digit number", instructions=None, worked_example="ex",
                   problems=[ExtractedProblem(number=1, prompt="30,000 + 100 + 4", correct_answer="30,104")])
_BAD = Extraction(title="t", instructions=None, worked_example=None,
                  problems=[ExtractedProblem(number=1, prompt="6 x 8", correct_answer="54")])


async def test_inserts_valid_worksheet(session, tmp_path):
    store = InMemoryObjectStore()
    out = await ingest_pdf(_make_pdf(tmp_path), session=session, extractor=FakeExtractor(_GOOD), store=store,
                           loader=_fake_loader)
    assert out.status == "inserted"
    skills = (await session.exec(select(Skill))).all()
    problems = (await session.exec(select(Problem))).all()
    assert skills[0].skill_key == "place-value-5-digit"
    assert len(problems) == 1
    assert any(k.startswith("worksheets/") for k in store.objects)


async def test_second_ingest_same_pdf_skips(session, tmp_path):
    store = InMemoryObjectStore()
    path = _make_pdf(tmp_path)
    await ingest_pdf(path, session=session, extractor=FakeExtractor(_GOOD), store=store, loader=_fake_loader)
    out = await ingest_pdf(path, session=session, extractor=FakeExtractor(_GOOD), store=store, loader=_fake_loader)
    assert out.status == "skipped"
    assert len((await session.exec(select(Worksheet))).all()) == 1


async def test_invalid_extraction_quarantined(session, tmp_path):
    out = await ingest_pdf(_make_pdf(tmp_path), session=session, extractor=FakeExtractor(_BAD),
                           store=InMemoryObjectStore(), loader=_fake_loader)
    assert out.status == "quarantined"
    q = (await session.exec(select(QuarantinedExtraction))).all()
    assert "arithmetic" in q[0].reason
    assert len((await session.exec(select(Worksheet))).all()) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ingest.orchestrator'`

- [ ] **Step 3: Write `app/ingest/orchestrator.py`**

```python
import hashlib
from dataclasses import dataclass

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.ingest.extractor import Extractor
from app.ingest.pdf import PdfPages, load_pdf
from app.ingest.taxonomy import parse_filename
from app.ingest.validate import validate
from app.models import Problem, QuarantinedExtraction, Skill, Worksheet
from app.storage import ObjectStore


@dataclass(frozen=True)
class IngestOutcome:
    status: str  # "inserted" | "skipped" | "quarantined"
    worksheet_id: str | None
    reason: str | None


async def _get_or_create_skill(session: AsyncSession, tax) -> Skill:
    existing = (await session.exec(select(Skill).where(Skill.skill_key == tax.skill_key))).first()
    if existing:
        return existing
    skill = Skill(grade=tax.grade, topic=tax.topic, skill_key=tax.skill_key, label=tax.skill_key)
    session.add(skill)
    await session.flush()
    return skill


async def ingest_pdf(path, *, session: AsyncSession, extractor: Extractor, store: ObjectStore,
                     loader=load_pdf) -> IngestOutcome:
    with open(path, "rb") as fh:
        raw = fh.read()
    sha = hashlib.sha256(raw).hexdigest()
    if (await session.exec(select(Worksheet).where(Worksheet.pdf_sha256 == sha))).first():
        return IngestOutcome("skipped", None, None)

    tax = parse_filename(path)
    pages: PdfPages = loader(path)
    extraction = extractor.extract(pages)
    result = validate(extraction)
    if not result.ok:
        session.add(QuarantinedExtraction(pdf_path=path, pdf_sha256=sha, reason=result.reason or "invalid",
                                          raw_json=extraction.model_dump()))
        await session.commit()
        return IngestOutcome("quarantined", None, result.reason)

    skill = await _get_or_create_skill(session, tax)
    if skill.label == skill.skill_key and extraction.title:
        skill.label = extraction.title
    r2_key = store.put(f"worksheets/{sha}.pdf", raw, "application/pdf")
    ws = Worksheet(skill_id=skill.id, source="k5", variant=tax.variant, title=extraction.title,
                   worked_example=extraction.worked_example, source_pdf_r2_key=r2_key,
                   problem_count=len(extraction.problems), pdf_sha256=sha)
    session.add(ws)
    await session.flush()
    for p in extraction.problems:
        session.add(Problem(worksheet_id=ws.id, number=p.number, prompt=p.prompt,
                            correct_answer=p.correct_answer, extraction_confidence=p.confidence))
    await session.commit()
    return IngestOutcome("inserted", ws.id, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_orchestrator.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/ingest/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(ingest): orchestrator — idempotent insert/skip/quarantine"
```

---

### Task 9: Catalog read API

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/catalog.py`
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/test_catalog_api.py`

**Interfaces:**
- Consumes: `app.db.get_session`, models.
- Produces: router at `/api` with `GET /api/skills?grade=`, `GET /api/skills/{skill_id}/worksheets`, `GET /api/worksheets/{worksheet_id}` (worksheet + ordered problems). `create_app()` includes the router and overridable `get_session` dependency.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_catalog_api.py
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.main import create_app
from app.models import Problem, Skill, Worksheet


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        skill = Skill(grade=5, topic="place-value-rounding", skill_key="place-value-5-digit", label="Build a 5-digit number")
        s.add(skill); await s.flush()
        ws = Worksheet(skill_id=skill.id, source="k5", variant="a", title="Build a 5-digit number",
                       problem_count=1, pdf_sha256="sha-a")
        s.add(ws); await s.flush()
        s.add(Problem(worksheet_id=ws.id, number=1, prompt="30,000 + 100 + 4", correct_answer="30,104"))
        await s.commit()

    async def _override():
        async with factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_list_skills_by_grade(client):
    resp = await client.get("/api/skills?grade=5")
    assert resp.status_code == 200
    assert resp.json()[0]["skill_key"] == "place-value-5-digit"


async def test_worksheet_detail_includes_problems(client):
    skills = (await client.get("/api/skills?grade=5")).json()
    wss = (await client.get(f"/api/skills/{skills[0]['id']}/worksheets")).json()
    detail = (await client.get(f"/api/worksheets/{wss[0]['id']}")).json()
    assert detail["title"] == "Build a 5-digit number"
    assert detail["problems"][0]["correct_answer"] == "30,104"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_catalog_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.api.catalog'`

- [ ] **Step 3: Write `app/api/catalog.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.models import Problem, Skill, Worksheet

router = APIRouter(prefix="/api")


@router.get("/skills")
async def list_skills(grade: int | None = None, session: AsyncSession = Depends(get_session)):
    stmt = select(Skill)
    if grade is not None:
        stmt = stmt.where(Skill.grade == grade)
    return (await session.exec(stmt)).all()


@router.get("/skills/{skill_id}/worksheets")
async def list_worksheets(skill_id: str, session: AsyncSession = Depends(get_session)):
    return (await session.exec(select(Worksheet).where(Worksheet.skill_id == skill_id))).all()


@router.get("/worksheets/{worksheet_id}")
async def worksheet_detail(worksheet_id: str, session: AsyncSession = Depends(get_session)):
    ws = (await session.exec(select(Worksheet).where(Worksheet.id == worksheet_id))).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="worksheet not found")
    problems = (await session.exec(
        select(Problem).where(Problem.worksheet_id == worksheet_id).order_by(Problem.number)
    )).all()
    return {**ws.model_dump(), "problems": [p.model_dump() for p in problems]}
```

- [ ] **Step 4: Register the router in `app/main.py`**

```python
# backend/app/main.py
from fastapi import FastAPI

from app.api.catalog import router as catalog_router


def create_app() -> FastAPI:
    app = FastAPI(title="Socrates")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(catalog_router)
    return app


app = create_app()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_catalog_api.py tests/test_health.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api backend/app/main.py backend/tests/test_catalog_api.py
git commit -m "feat(api): catalog read endpoints (skills/worksheets/worksheet detail)"
```

---

### Task 10: Ingestion CLI + Alembic baseline

**Files:**
- Create: `backend/app/cli.py`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Test: `backend/tests/test_cli.py`

**Interfaces:**
- Consumes: `ingest_pdf`, `GeminiExtractor`/`FakeExtractor`, `R2ObjectStore`/`InMemoryObjectStore`, `app.db`.
- Produces: `app.cli:discover_pdfs(root: str) -> list[str]` and `app.cli:main(argv: list[str]) -> int` exposing `ingest <root> [--dry-run]`. Default run uses `GeminiExtractor` + `R2ObjectStore`; `--dry-run` uses `InMemoryObjectStore` and prints a per-status summary.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cli.py
from pathlib import Path

from app.cli import discover_pdfs


def test_discover_pdfs_finds_only_grade_pdfs(tmp_path):
    (tmp_path / "topic").mkdir()
    (tmp_path / "topic" / "grade-5-foo-a.pdf").write_bytes(b"%PDF")
    (tmp_path / "topic" / "notes.txt").write_text("x")
    found = discover_pdfs(str(tmp_path))
    assert found == [str(tmp_path / "topic" / "grade-5-foo-a.pdf")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.cli'`

- [ ] **Step 3: Write `app/cli.py`**

```python
import argparse
import asyncio
from collections import Counter
from pathlib import Path

from app.db import create_all, engine
from app.ingest.gemini_extractor import GeminiExtractor
from app.ingest.orchestrator import ingest_pdf
from app.config import settings
from app.storage import InMemoryObjectStore, R2ObjectStore
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession


def discover_pdfs(root: str) -> list[str]:
    return sorted(str(p) for p in Path(root).rglob("grade-*-*.pdf"))


async def _run(root: str, dry_run: bool) -> int:
    await create_all()
    extractor = GeminiExtractor(settings.gemini_api_key)
    store = InMemoryObjectStore() if dry_run else R2ObjectStore()
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    counts: Counter[str] = Counter()
    for path in discover_pdfs(root):
        async with factory() as session:
            outcome = await ingest_pdf(path, session=session, extractor=extractor, store=store)
        counts[outcome.status] += 1
        print(f"{outcome.status:11} {path}")
    print(f"\nSummary: {dict(counts)}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="socrates")
    sub = parser.add_subparsers(dest="command", required=True)
    ing = sub.add_parser("ingest")
    ing.add_argument("root")
    ing.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "ingest":
        return asyncio.run(_run(args.root, args.dry_run))
    return 1


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Initialize Alembic baseline for Postgres prod**

Run:
```bash
cd backend && uv run alembic init migrations
```
Then edit `migrations/env.py` to import metadata and use `settings.database_url`:
```python
# in migrations/env.py — replace target_metadata and url wiring
from app.config import settings
from app.models import SQLModel  # noqa: F401  (registers tables)
from sqlmodel import SQLModel as _SQLModel

target_metadata = _SQLModel.metadata
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", "").replace("+aiosqlite", ""))
```
Generate the baseline migration:
```bash
cd backend && DATABASE_URL=postgresql://localhost/socrates uv run alembic revision --autogenerate -m "baseline catalog"
```
Expected: a migration file under `migrations/versions/` creating `skill`, `worksheet`, `problem`, `quarantined_extraction`.

- [ ] **Step 6: Run the full test suite**

Run: `cd backend && uv run pytest -v`
Expected: PASS (all tasks)

- [ ] **Step 7: Commit**

```bash
git add backend/app/cli.py backend/alembic.ini backend/migrations backend/tests/test_cli.py
git commit -m "feat(ingest): CLI runner + Alembic baseline migration"
```

---

### Task 11: End-to-end dry-run on real PDFs (manual verification)

**Files:**
- Create: `backend/README.md` (run instructions)

**Interfaces:**
- Consumes: everything above.
- Produces: documented commands; a verified dry-run over the real library.

- [ ] **Step 1: Document setup + run in `backend/README.md`**

```markdown
# Socrates backend

## Setup
- Install poppler (`pdftotext`) and `uv`.
- `cd backend && uv sync`
- Set `GEMINI_API_KEY` and (for non-dry runs) `R2_*` + `DATABASE_URL` in `.env`.

## Ingest the worksheet library
Dry run (SQLite, in-memory storage, real Gemini extraction):
    cd backend && uv run python -m app.cli ingest ../worksheets --dry-run
    cd backend && uv run python -m app.cli ingest ../worksheet-g3 --dry-run

## Tests
    cd backend && uv run pytest -v
```

- [ ] **Step 2: Run a dry-run over a single topic and inspect output**

Run:
```bash
cd backend && GEMINI_API_KEY=$GEMINI_API_KEY uv run python -m app.cli ingest ../worksheets/place-value-rounding --dry-run
```
Expected: each PDF prints `inserted` / `skipped` / `quarantined`; final `Summary: {...}` with the large majority `inserted` and a small quarantine count. Spot-check that quarantined sheets are genuinely hard layouts (review `quarantined_extraction` rows), not a systemic parser bug.

- [ ] **Step 3: Commit**

```bash
git add backend/README.md
git commit -m "docs(backend): run instructions + verified ingestion dry-run"
```

---

## Notes for later plans (not in scope here)

- **Print + QR (Plan 2):** `Attempt` model, strip page 2, render QR encoding `attempt_id`, store print PDF in R2.
- **Grading (Plan 3):** reuse `ObjectStore` + a `Vision` interface mirroring `Extractor`; resolve QR → `Attempt` → known `Problem`s; compare; write `Submission` / `ProblemResult`.
- **Skill labels:** ingestion seeds `Skill.label` from the first worksheet title; a later pass can dedupe/curate labels per `skill_key`.
- **Decision vs spec §13:** text extraction uses poppler `pdftotext` per page (as specced); PyMuPDF handles split + render only.
