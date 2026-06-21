import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Attempt, Child, Skill, Worksheet


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def test_child_attempt_roundtrip(session):
    skill = Skill(grade=5, topic="t", skill_key="k", label="L")
    session.add(skill); await session.flush()
    ws = Worksheet(skill_id=skill.id, source="k5", title="W", problem_count=1, pdf_sha256="sha1")
    session.add(ws); await session.flush()
    child = Child(name="Ada", grade=5)
    session.add(child); await session.flush()
    attempt = Attempt(child_id=child.id, worksheet_id=ws.id, status="printed",
                      print_pdf_r2_key="prints/x.pdf")
    session.add(attempt); await session.commit()

    rows = (await session.exec(select(Attempt))).all()
    assert len(rows) == 1
    assert rows[0].status == "printed"
    assert rows[0].child_id == child.id
    assert len(rows[0].id) == 32
    assert rows[0].scanned_at is None
