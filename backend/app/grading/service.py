import asyncio

from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.grading.compare import answers_match, parses_as_number
from app.grading.vision import ProblemPrompt, Vision
from app.models import Attempt, Problem, ProblemResult, Submission, _id, _utcnow
from app.storage import ObjectStore

LOW_CONFIDENCE_THRESHOLD = 0.7
_MIME_BY_EXT = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}


def _norm_code(s: str) -> str:
    return "".join(c for c in s.upper() if c.isalnum())


class ProblemResultOut(BaseModel):
    problem_id: str
    number: int
    read_answer: str | None
    is_correct: bool
    confidence: float
    match_method: str
    needs_review: bool
    correct_answer: str | None = None


class GradeResult(BaseModel):
    submission_id: str
    attempt_id: str
    score_correct: int
    score_total: int
    needs_review_count: int
    identity_ok: bool = True  # did the code read off the photo match the attempt's code?
    results: list[ProblemResultOut]


async def grade_submission(*, session: AsyncSession, store: ObjectStore, vision: Vision,
                           attempt: Attempt, photo: bytes, ext: str,
                           ai_fallback: bool = False) -> GradeResult:
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

    # Advisory identity cross-check: the API already resolved the authoritative
    # attempt, so a misread/missing code never blocks grading — it just flags.
    identity_ok = True
    if read.printed_id and attempt.code:
        identity_ok = _norm_code(read.printed_id) == _norm_code(attempt.code)

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
            # Mismatch on a non-blank read. Trust the code for a clear numeric
            # difference; only consult Gemini when the code can't parse a side
            # (a format it doesn't understand) — unless ai_fallback forces it on.
            code_decisive = parses_as_number(read_answer) and parses_as_number(p.correct_answer)
            if ai_fallback or not code_decisive:
                is_correct = await asyncio.to_thread(vision.judge_equivalence, read_answer, p.correct_answer)
                method = "gemini_equiv"
            else:
                is_correct = False
                method = "normalized"
        else:
            is_correct = False
            method = "exact"

        needs_review = confidence < LOW_CONFIDENCE_THRESHOLD
        session.add(ProblemResult(submission_id=submission_id, problem_id=p.id,
                                  read_answer=read_answer, is_correct=is_correct,
                                  confidence=confidence, match_method=method, needs_review=needs_review))
        outs.append(ProblemResultOut(
            problem_id=p.id, number=p.number, read_answer=read_answer,
            is_correct=is_correct, confidence=confidence, match_method=method,
            needs_review=needs_review,
            correct_answer=(p.correct_answer if (read_answer is not None and not is_correct) else None),
        ))

    attempt.graded_at = _utcnow()
    attempt.status = "graded"
    session.add(attempt)
    await session.commit()

    return GradeResult(
        submission_id=submission_id, attempt_id=attempt.id,
        score_correct=sum(1 for o in outs if o.is_correct), score_total=len(outs),
        needs_review_count=sum(1 for o in outs if o.needs_review),
        identity_ok=identity_ok, results=outs,
    )
