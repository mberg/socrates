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
    await engine.dispose()


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
