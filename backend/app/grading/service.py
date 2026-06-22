import asyncio

from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.grading.compare import answers_match
from app.grading.vision import ProblemPrompt, Vision
from app.models import Attempt, Problem, ProblemResult, Submission, _id, _utcnow
from app.storage import ObjectStore

LOW_CONFIDENCE_THRESHOLD = 0.7
_MIME_BY_EXT = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}


class IdentityMismatch(Exception):
    pass


class ProblemResultOut(BaseModel):
    problem_id: str
    number: int
    read_answer: str | None
    is_correct: bool
    confidence: float
    match_method: str
    needs_review: bool


class GradeResult(BaseModel):
    submission_id: str
    attempt_id: str
    score_correct: int
    score_total: int
    needs_review_count: int
    results: list[ProblemResultOut]


async def grade_submission(*, session: AsyncSession, store: ObjectStore, vision: Vision,
                           attempt: Attempt, photo: bytes, ext: str) -> GradeResult:
    submission_id = _id()
    key = f"submissions/{submission_id}.{ext}"
    content_type = _MIME_BY_EXT.get(ext.lower(), "application/octet-stream")
    await asyncio.to_thread(store.put, key, photo, content_type)
    submission = Submission(id=submission_id, attempt_id=attempt.id, photo_r2_key=key)
    attempt.scanned_at = _utcnow()
    attempt.status = "scanned"
    session.add(submission)
    session.add(attempt)
    await session.commit()

    problems = (await session.exec(
        select(Problem).where(Problem.worksheet_id == attempt.worksheet_id).order_by(Problem.number)
    )).all()

    read = await asyncio.to_thread(
        vision.read, photo, [ProblemPrompt(number=p.number, prompt=p.prompt) for p in problems]
    )

    if read.printed_id is not None and read.printed_id.strip().lower() != attempt.id:
        raise IdentityMismatch(f"photo printed_id {read.printed_id!r} != attempt {attempt.id}")

    reads = {r.number: r for r in read.problems}
    outs: list[ProblemResultOut] = []
    for p in problems:
        r = reads.get(p.number)
        read_answer = r.read_answer if r else None
        confidence = r.confidence if r else 0.0

        if answers_match(read_answer, p.correct_answer):
            is_correct = True
            method = "exact" if (read_answer or "").strip() == p.correct_answer.strip() else "normalized"
        elif read_answer is not None:
            is_correct = await asyncio.to_thread(vision.judge_equivalence, read_answer, p.correct_answer)
            method = "gemini_equiv"
        else:
            is_correct = False
            method = "exact"

        needs_review = confidence < LOW_CONFIDENCE_THRESHOLD
        session.add(ProblemResult(submission_id=submission_id, problem_id=p.id,
                                  read_answer=read_answer, is_correct=is_correct,
                                  confidence=confidence, match_method=method, needs_review=needs_review))
        outs.append(ProblemResultOut(problem_id=p.id, number=p.number, read_answer=read_answer,
                                     is_correct=is_correct, confidence=confidence,
                                     match_method=method, needs_review=needs_review))

    attempt.graded_at = _utcnow()
    attempt.status = "graded"
    session.add(attempt)
    await session.commit()

    return GradeResult(
        submission_id=submission_id, attempt_id=attempt.id,
        score_correct=sum(1 for o in outs if o.is_correct), score_total=len(outs),
        needs_review_count=sum(1 for o in outs if o.needs_review), results=outs,
    )
