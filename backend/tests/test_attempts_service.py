import fitz
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Attempt, Child, Skill, Worksheet
from app.services.attempts import create_attempt
from app.storage import InMemoryObjectStore


def _two_page_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "WORKSHEET")
    doc.new_page().insert_text((72, 72), "ANSWER KEY")
    return doc.tobytes()


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def test_create_attempt_generates_and_stores_print(session):
    store = InMemoryObjectStore()
    store.put("worksheets/sha9.pdf", _two_page_pdf(), "application/pdf")
    skill = Skill(grade=5, topic="t", skill_key="k", label="L"); session.add(skill); await session.flush()
    ws = Worksheet(skill_id=skill.id, source="k5", title="W", problem_count=1,
                   pdf_sha256="sha9", source_pdf_r2_key="worksheets/sha9.pdf")
    session.add(ws); await session.flush()
    child = Child(name="Ada", grade=5); session.add(child); await session.commit()

    attempt = await create_attempt(session=session, store=store, child=child, worksheet_id=ws.id)

    assert attempt.status == "printed"
    assert attempt.printed_at is not None
    assert attempt.print_pdf_r2_key == f"prints/{attempt.id}.pdf"
    # short, unambiguous code generated for the print stamp + QR
    assert attempt.code is not None and len(attempt.code) == 5
    assert all(c in "23456789ABCDEFGHJKMNPQRSTUVWXYZ" for c in attempt.code)
    # the print pdf was stored, is 1 page, and excludes the answer key
    pdf = store.get(attempt.print_pdf_r2_key)
    doc = fitz.open(stream=pdf, filetype="pdf")
    assert doc.page_count == 1
    assert "ANSWER KEY" not in doc[0].get_text()


async def test_create_attempt_unknown_worksheet_raises(session):
    child = Child(name="A", grade=5); session.add(child); await session.commit()
    with pytest.raises(LookupError):
        await create_attempt(session=session, store=InMemoryObjectStore(), child=child, worksheet_id="missing")
