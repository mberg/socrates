# backend/tests/test_models.py
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel, select

from app.models import Problem, Skill, Worksheet


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


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
