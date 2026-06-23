from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import Attempt, GuidanceSession, Problem
from app.tutor.base import Tutor
from app.tutor.gemini import GeminiTutor
from app.tutor.service import (GuidanceSessionView, add_turn, session_view, start_session)

router = APIRouter(prefix="/api")


def get_tutor() -> Tutor:
    return GeminiTutor(
        api_key=settings.gemini_api_key, model=settings.gemini_model,
        use_vertex=settings.gemini_use_vertex,
        project=settings.gemini_vertex_project or None,
        location=settings.gemini_vertex_location or None,
    )


class TurnIn(BaseModel):
    text: str | None = None
    input_source: str | None = None
    advance: bool = False
    reveal: bool = False


async def _get_session_or_404(session: AsyncSession, session_id: str) -> GuidanceSession:
    gs = (await session.exec(select(GuidanceSession).where(GuidanceSession.id == session_id))).first()
    if gs is None:
        raise HTTPException(status_code=404, detail="guidance session not found")
    return gs


@router.post("/children/{child_id}/attempts/{attempt_id}/problems/{problem_id}/guidance",
             response_model=GuidanceSessionView)
async def start(child_id: str, attempt_id: str, problem_id: str,
                session: AsyncSession = Depends(get_session),
                tutor: Tutor = Depends(get_tutor)):
    attempt = (await session.exec(
        select(Attempt).where(Attempt.id == attempt_id, Attempt.child_id == child_id))).first()
    if attempt is None:
        raise HTTPException(status_code=404, detail="attempt not found")
    problem = (await session.exec(
        select(Problem).where(Problem.id == problem_id,
                              Problem.worksheet_id == attempt.worksheet_id))).first()
    if problem is None:
        raise HTTPException(status_code=404, detail="problem not found for this attempt")
    gs = await start_session(session=session, tutor=tutor, child_id=child_id,
                             attempt_id=attempt_id, problem_id=problem_id)
    return await session_view(session, gs)


@router.post("/guidance/{session_id}/turns", response_model=GuidanceSessionView)
async def post_turn(session_id: str, body: TurnIn,
                    session: AsyncSession = Depends(get_session),
                    tutor: Tutor = Depends(get_tutor)):
    gs = await _get_session_or_404(session, session_id)
    gs = await add_turn(session=session, tutor=tutor, gs=gs, text=body.text,
                        input_source=body.input_source, advance=body.advance, reveal=body.reveal)
    return await session_view(session, gs)


@router.get("/guidance/{session_id}", response_model=GuidanceSessionView)
async def replay(session_id: str, session: AsyncSession = Depends(get_session)):
    gs = await _get_session_or_404(session, session_id)
    return await session_view(session, gs)


@router.post("/guidance/{session_id}/resolve", response_model=GuidanceSessionView)
async def resolve(session_id: str, session: AsyncSession = Depends(get_session)):
    gs = await _get_session_or_404(session, session_id)
    gs.resolved = True
    session.add(gs)
    await session.commit()
    return await session_view(session, gs)
