from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.models import Attempt, Child
from app.services.attempts import create_attempt
from app.storage import ObjectStore, default_store

router = APIRouter(prefix="/api")


def get_store() -> ObjectStore:
    return default_store()


class ChildIn(BaseModel):
    name: str
    grade: int


class AttemptIn(BaseModel):
    worksheet_id: str


@router.post("/children")
async def create_child(body: ChildIn, session: AsyncSession = Depends(get_session)):
    child = Child(name=body.name, grade=body.grade)
    session.add(child)
    await session.commit()
    return child


@router.get("/children")
async def list_children(session: AsyncSession = Depends(get_session)):
    return (await session.exec(select(Child))).all()


@router.post("/children/{child_id}/attempts")
async def create_child_attempt(child_id: str, body: AttemptIn,
                               session: AsyncSession = Depends(get_session),
                               store: ObjectStore = Depends(get_store)):
    child = (await session.exec(select(Child).where(Child.id == child_id))).first()
    if child is None:
        raise HTTPException(status_code=404, detail="child not found")
    try:
        return await create_attempt(session=session, store=store, child=child,
                                    worksheet_id=body.worksheet_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="worksheet not found")


@router.get("/children/{child_id}/attempts")
async def list_child_attempts(child_id: str, session: AsyncSession = Depends(get_session)):
    return (await session.exec(select(Attempt).where(Attempt.child_id == child_id))).all()


@router.get("/attempts/{attempt_id}/print")
async def download_print(attempt_id: str, session: AsyncSession = Depends(get_session),
                         store: ObjectStore = Depends(get_store)):
    attempt = (await session.exec(select(Attempt).where(Attempt.id == attempt_id))).first()
    if attempt is None or attempt.print_pdf_r2_key is None:
        raise HTTPException(status_code=404, detail="attempt or print not found")
    import asyncio
    pdf = await asyncio.to_thread(store.get, attempt.print_pdf_r2_key)
    return Response(content=pdf, media_type="application/pdf")
