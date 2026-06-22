from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.children import get_store
from app.config import settings
from app.db import get_session
from app.grading.service import GradeResult, ProblemResultOut, grade_submission
from app.grading.vision import GeminiVision, Vision
from app.models import Attempt, Problem, ProblemResult, Skill, Submission, Worksheet
from app.storage import ObjectStore

router = APIRouter(prefix="/api")


def get_vision() -> Vision:
    return GeminiVision(
        api_key=settings.gemini_api_key, model=settings.gemini_model,
        use_vertex=settings.gemini_use_vertex,
        project=settings.gemini_vertex_project or None,
        location=settings.gemini_vertex_location or None,
    )


@router.post("/children/{child_id}/attempts/{attempt_id}/submissions")
async def create_submission(
    child_id: str, attempt_id: str,
    file: UploadFile = File(...),
    ai_fallback: bool = Form(False),
    session: AsyncSession = Depends(get_session),
    store: ObjectStore = Depends(get_store),
    vision: Vision = Depends(get_vision),
) -> GradeResult:
    attempt = (await session.exec(
        select(Attempt).where(Attempt.id == attempt_id, Attempt.child_id == child_id)
    )).first()
    if attempt is None:
        raise HTTPException(status_code=404, detail="attempt not found")
    photo = await file.read()
    ext = (file.filename or "photo.jpg").rsplit(".", 1)[-1].lower()
    return await grade_submission(session=session, store=store, vision=vision,
                                  attempt=attempt, photo=photo, ext=ext, ai_fallback=ai_fallback)


class ScoreSummary(BaseModel):
    attempt_id: str
    code: str | None
    worksheet_title: str
    section: str
    score_correct: int
    score_total: int
    score_attempted: int  # problems with a non-blank read
    graded_at: str | None


@router.get("/children/{child_id}/scores", response_model=list[ScoreSummary])
async def child_scores(child_id: str, session: AsyncSession = Depends(get_session)):
    attempts = (await session.exec(
        select(Attempt).where(Attempt.child_id == child_id).order_by(Attempt.graded_at.desc())
    )).all()
    out: list[ScoreSummary] = []
    for att in attempts:
        sub = (await session.exec(
            select(Submission)
            .where(Submission.attempt_id == att.id)
            .where(Submission.id.in_(select(ProblemResult.submission_id)))
            .order_by(Submission.created_at.desc())
        )).first()
        if sub is None:
            continue  # not graded
        prs = (await session.exec(
            select(ProblemResult).where(ProblemResult.submission_id == sub.id)
        )).all()
        ws = (await session.exec(select(Worksheet).where(Worksheet.id == att.worksheet_id))).first()
        skill = (await session.exec(select(Skill).where(Skill.id == ws.skill_id))).first() if ws else None
        out.append(ScoreSummary(
            attempt_id=att.id,
            code=att.code,
            worksheet_title=ws.title if ws else "(unknown)",
            section=skill.label if skill else "",
            score_correct=sum(1 for r in prs if r.is_correct),
            score_total=len(prs),
            score_attempted=sum(1 for r in prs if r.read_answer is not None),
            graded_at=att.graded_at.isoformat() if att.graded_at else None,
        ))
    return out


@router.get("/attempts/{attempt_id}/results")
async def get_results(attempt_id: str, session: AsyncSession = Depends(get_session)) -> GradeResult:
    sub = (await session.exec(
        select(Submission)
        .where(Submission.attempt_id == attempt_id)
        .where(Submission.id.in_(select(ProblemResult.submission_id)))
        .order_by(Submission.created_at.desc())
    )).first()
    if sub is None:
        raise HTTPException(status_code=404, detail="no submission for attempt")
    rows = (await session.exec(
        select(ProblemResult, Problem)
        .where(ProblemResult.submission_id == sub.id)
        .join(Problem, Problem.id == ProblemResult.problem_id)
        .order_by(Problem.number)
    )).all()
    results = [ProblemResultOut(
        problem_id=pr.problem_id, number=p.number, read_answer=pr.read_answer,
        is_correct=pr.is_correct, confidence=pr.confidence, match_method=pr.match_method,
        needs_review=pr.needs_review,
        correct_answer=(p.correct_answer if (pr.read_answer is not None and not pr.is_correct) else None),
    ) for pr, p in rows]
    return GradeResult(
        submission_id=sub.id, attempt_id=attempt_id,
        score_correct=sum(1 for r in results if r.is_correct), score_total=len(results),
        needs_review_count=sum(1 for r in results if r.needs_review), results=results,
    )
