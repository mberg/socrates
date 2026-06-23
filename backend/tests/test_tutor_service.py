import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import (Attempt, Child, Problem, ProblemResult, Submission,
                        TutorTurn, Worksheet)
from app.tutor.base import FakeTutor
from app.tutor.service import add_turn, build_context, start_session


@pytest.fixture
async def fx():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        ws = Worksheet(skill_id="sk", source="k5", title="W", problem_count=1,
                       pdf_sha256="sha", worked_example="3 x 4 = 12")
        s.add(ws); await s.flush()
        prob = Problem(worksheet_id=ws.id, number=3, prompt="3 x 4", correct_answer="12")
        s.add(prob); await s.flush()
        child = Child(name="Ada", grade=3); s.add(child); await s.flush()
        att = Attempt(child_id=child.id, worksheet_id=ws.id); s.add(att); await s.flush()
        sub = Submission(attempt_id=att.id, photo_r2_key="k"); s.add(sub); await s.flush()
        pr = ProblemResult(submission_id=sub.id, problem_id=prob.id, read_answer="7",
                           is_correct=False, confidence=0.9, match_method="normalized")
        s.add(pr); await s.commit()
        yield factory, child.id, att.id, prob.id, ws, prob, child
    await engine.dispose()


def test_build_context_gates_correct_answer_on_tier3(fx):
    # build_context is pure — exercise it directly with simple stand-ins.
    class P: prompt = "3 x 4"; correct_answer = "12"
    class W: worked_example = "3 x 4 = 12"
    class C: name = "Ada"; grade = 3
    assert build_context(P, W, C, "7", tier=1).correct_answer is None
    assert build_context(P, W, C, "7", tier=2).correct_answer is None
    assert build_context(P, W, C, "7", tier=3).correct_answer == "12"


async def test_start_then_advance_to_tier3_reveals(fx):
    factory, child_id, att_id, prob_id, *_ = fx
    async with factory() as s:
        gs = await start_session(session=s, tutor=FakeTutor(), child_id=child_id,
                                 attempt_id=att_id, problem_id=prob_id)
        assert gs.max_tier_reached == 1
        # advance twice to reach Tier 3
        gs = await add_turn(session=s, tutor=FakeTutor(), gs=gs, text=None, input_source=None, advance=True)
        gs = await add_turn(session=s, tutor=FakeTutor(), gs=gs, text=None, input_source=None, advance=True)
        assert gs.max_tier_reached == 3
    # one more advance must not exceed 3
    async with factory() as s:
        gs2 = await start_session(session=s, tutor=FakeTutor(), child_id=child_id,
                                  attempt_id=att_id, problem_id=prob_id)
        for _ in range(5):
            gs2 = await add_turn(session=s, tutor=FakeTutor(), gs=gs2, text=None, input_source=None, advance=True)
        assert gs2.max_tier_reached == 3


async def test_reveal_states_answer_and_skips_ai(fx):
    """'Show me the answer' must deterministically present the correct answer
    without calling the tutor model (which can loop on guiding questions)."""
    factory, child_id, att_id, prob_id, *_ = fx

    class BoomTutor:
        async def respond(self, *a, **k):
            raise AssertionError("the AI must not be called when revealing the answer")

    async with factory() as s:
        gs = await start_session(session=s, tutor=FakeTutor(), child_id=child_id,
                                 attempt_id=att_id, problem_id=prob_id)
        gs = await add_turn(session=s, tutor=BoomTutor(), gs=gs, text=None,
                            input_source=None, advance=False, reveal=True)
        assert gs.max_tier_reached == 3
        turns = (await s.exec(
            select(TutorTurn).where(TutorTurn.session_id == gs.id).order_by(TutorTurn.created_at)
        )).all()
        last = turns[-1]
        assert last.role == "tutor"
        assert last.tier == 3
        assert "12" in last.text  # the problem's correct_answer
