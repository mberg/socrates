from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import (Attempt, Child, GuidanceSession, Problem, ProblemResult,
                        Submission, TutorTurn, Worksheet, _utcnow)
from app.tutor.base import Tutor, TutorContext, Turn
from app.tutor.visuals import validate_visuals


def validate_visuals_to_dicts(raw: list[dict]) -> list[dict]:
    return [v.model_dump(by_alias=True) for v in validate_visuals(raw)]


class TurnView(BaseModel):
    id: str
    role: str
    text: str
    input_source: str | None
    visuals: list[dict]
    tier: int
    created_at: str


class GuidanceSessionView(BaseModel):
    id: str
    problem_id: str
    problem_number: int
    problem_prompt: str
    max_tier_reached: int
    resolved: bool
    revealed_at: str | None
    turns: list[TurnView]


def build_context(problem, worksheet, child, child_answer: str | None, tier: int) -> TutorContext:
    return TutorContext(
        problem_prompt=problem.prompt,
        worked_example=getattr(worksheet, "worked_example", None),
        grade=child.grade,
        child_name=child.name,
        child_answer=child_answer,
        correct_answer=problem.correct_answer if tier >= 3 else None,
    )


async def _latest_read_answer(session: AsyncSession, attempt_id: str, problem_id: str) -> str | None:
    sub = (await session.exec(
        select(Submission)
        .where(Submission.attempt_id == attempt_id)
        .where(Submission.id.in_(select(ProblemResult.submission_id)))
        .order_by(Submission.created_at.desc())
    )).first()
    if sub is None:
        return None
    pr = (await session.exec(
        select(ProblemResult)
        .where(ProblemResult.submission_id == sub.id, ProblemResult.problem_id == problem_id)
    )).first()
    return pr.read_answer if pr else None


async def _persist_tutor_turn(session, tutor: Tutor, gs: GuidanceSession,
                              problem, worksheet, child, child_answer) -> None:
    history = [Turn(role=t.role, text=t.text) for t in (await session.exec(
        select(TutorTurn).where(TutorTurn.session_id == gs.id).order_by(TutorTurn.created_at)
    )).all()]
    ctx = build_context(problem, worksheet, child, child_answer, gs.max_tier_reached)
    reply = await tutor.respond(ctx, history, gs.max_tier_reached)
    visuals = [v.model_dump(by_alias=True) for v in validate_visuals(reply.visuals)]
    session.add(TutorTurn(session_id=gs.id, role="tutor", text=reply.say,
                          input_source=None, visuals=visuals, tier=gs.max_tier_reached))
    await session.commit()


async def _persist_reveal_turn(session, gs: GuidanceSession, problem) -> None:
    """Deterministically state the correct answer — no model call, no visual.

    "Show me the answer" must always reveal it; routing through the tutor model
    risks it looping on guiding questions instead of committing to the answer.
    No visual is attached: prompts are often word-problem sentences, and rendering
    those as TeX stacks the letters into garbage.
    """
    answer = problem.correct_answer or ""
    say = f"The answer is {answer}."
    session.add(TutorTurn(session_id=gs.id, role="tutor", text=say,
                          input_source=None, visuals=[], tier=gs.max_tier_reached))
    await session.commit()


async def _load_grounding(session, gs: GuidanceSession):
    problem = (await session.exec(select(Problem).where(Problem.id == gs.problem_id))).first()
    worksheet = (await session.exec(select(Worksheet).where(Worksheet.id == problem.worksheet_id))).first()
    child = (await session.exec(select(Child).where(Child.id == gs.child_id))).first()
    child_answer = await _latest_read_answer(session, gs.attempt_id, gs.problem_id)
    return problem, worksheet, child, child_answer


async def start_session(*, session: AsyncSession, tutor: Tutor, child_id: str,
                        attempt_id: str, problem_id: str) -> GuidanceSession:
    existing = (await session.exec(
        select(GuidanceSession)
        .where(GuidanceSession.child_id == child_id,
               GuidanceSession.attempt_id == attempt_id,
               GuidanceSession.problem_id == problem_id,
               GuidanceSession.resolved == False)  # noqa: E712
        .order_by(GuidanceSession.created_at.desc())
    )).first()
    if existing is not None:
        return existing

    # Resolve the ProblemResult this session addresses (latest graded submission).
    pr = None
    sub = (await session.exec(
        select(Submission).where(Submission.attempt_id == attempt_id)
        .where(Submission.id.in_(select(ProblemResult.submission_id)))
        .order_by(Submission.created_at.desc())
    )).first()
    if sub is not None:
        pr = (await session.exec(
            select(ProblemResult).where(ProblemResult.submission_id == sub.id,
                                        ProblemResult.problem_id == problem_id)
        )).first()

    gs = GuidanceSession(child_id=child_id, attempt_id=attempt_id, problem_id=problem_id,
                         problem_result_id=pr.id if pr else "")
    session.add(gs)
    await session.commit()
    problem, worksheet, child, child_answer = await _load_grounding(session, gs)
    await _persist_tutor_turn(session, tutor, gs, problem, worksheet, child, child_answer)
    return gs


async def add_turn(*, session: AsyncSession, tutor: Tutor, gs: GuidanceSession,
                   text: str | None, input_source: str | None, advance: bool,
                   reveal: bool = False) -> GuidanceSession:
    # reveal ("show me the answer") jumps straight to Tier 3; advance steps one tier.
    if reveal:
        if gs.max_tier_reached < 3:
            gs.max_tier_reached = 3
        if gs.revealed_at is None:  # stamp the first time the answer was revealed
            gs.revealed_at = _utcnow()
        session.add(gs)
        await session.commit()
    elif advance and gs.max_tier_reached < 3:
        gs.max_tier_reached += 1
        session.add(gs)
        await session.commit()
    if text:
        session.add(TutorTurn(session_id=gs.id, role="child", text=text,
                              input_source=input_source or "typed", visuals=[], tier=gs.max_tier_reached))
        await session.commit()
    problem, worksheet, child, child_answer = await _load_grounding(session, gs)
    if reveal:
        await _persist_reveal_turn(session, gs, problem)
    else:
        await _persist_tutor_turn(session, tutor, gs, problem, worksheet, child, child_answer)
    return gs


async def session_view(session: AsyncSession, gs: GuidanceSession) -> GuidanceSessionView:
    problem = (await session.exec(select(Problem).where(Problem.id == gs.problem_id))).first()
    turns = (await session.exec(
        select(TutorTurn).where(TutorTurn.session_id == gs.id).order_by(TutorTurn.created_at)
    )).all()
    return GuidanceSessionView(
        id=gs.id, problem_id=gs.problem_id, problem_number=problem.number,
        problem_prompt=problem.prompt, max_tier_reached=gs.max_tier_reached, resolved=gs.resolved,
        revealed_at=gs.revealed_at.isoformat() if gs.revealed_at else None,
        turns=[TurnView(id=t.id, role=t.role, text=t.text, input_source=t.input_source,
                        visuals=validate_visuals_to_dicts(t.visuals), tier=t.tier,
                        created_at=t.created_at.isoformat()) for t in turns],
    )
