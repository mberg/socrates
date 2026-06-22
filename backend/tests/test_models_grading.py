import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import (Attempt, Child, ProblemResult, Skill, Submission, Worksheet, Problem)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def test_submission_and_problemresult_roundtrip(session):
    skill = Skill(grade=5, topic="t", skill_key="k", label="L"); session.add(skill); await session.flush()
    ws = Worksheet(skill_id=skill.id, source="k5", title="W", problem_count=1, pdf_sha256="sha")
    session.add(ws); await session.flush()
    problem = Problem(worksheet_id=ws.id, number=1, prompt="2+2", correct_answer="4")
    child = Child(name="Ada", grade=5)
    session.add(problem); session.add(child); await session.flush()
    attempt = Attempt(child_id=child.id, worksheet_id=ws.id)
    session.add(attempt); await session.flush()

    sub = Submission(attempt_id=attempt.id, photo_r2_key="submissions/x.jpg")
    session.add(sub); await session.flush()
    pr = ProblemResult(submission_id=sub.id, problem_id=problem.id, read_answer="4",
                       is_correct=True, confidence=0.9, match_method="exact", needs_review=False)
    session.add(pr); await session.commit()

    got = (await session.exec(select(ProblemResult).where(ProblemResult.submission_id == sub.id))).one()
    assert got.is_correct is True
    assert got.match_method == "exact"
    assert got.read_answer == "4"


async def test_problemresult_read_answer_nullable(session):
    skill = Skill(grade=5, topic="t", skill_key="k", label="L"); session.add(skill); await session.flush()
    ws = Worksheet(skill_id=skill.id, source="k5", title="W", problem_count=1, pdf_sha256="s2")
    session.add(ws); await session.flush()
    problem = Problem(worksheet_id=ws.id, number=1, prompt="2+2", correct_answer="4")
    child = Child(name="B", grade=5); session.add(problem); session.add(child); await session.flush()
    attempt = Attempt(child_id=child.id, worksheet_id=ws.id); session.add(attempt); await session.flush()
    sub = Submission(attempt_id=attempt.id, photo_r2_key="submissions/y.jpg"); session.add(sub); await session.flush()
    pr = ProblemResult(submission_id=sub.id, problem_id=problem.id, read_answer=None,
                       is_correct=False, confidence=0.2, match_method="exact", needs_review=True)
    session.add(pr); await session.commit()
    assert pr.read_answer is None and pr.needs_review is True
