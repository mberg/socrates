import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.models import Attempt, Child, Skill, Worksheet
from app.security import hash_pin, verify_pin
from app.services.attempts import create_attempt
from app.storage import ObjectStore, default_store

router = APIRouter(prefix="/api")


def get_store() -> ObjectStore:
    return default_store()


class ChildIn(BaseModel):
    name: str
    grade: int
    pin: str | None = None


class ChildOut(BaseModel):
    id: str
    name: str
    grade: int
    has_pin: bool


class PinIn(BaseModel):
    pin: str


class PinResult(BaseModel):
    ok: bool


class AttemptIn(BaseModel):
    worksheet_id: str


class AttemptOut(BaseModel):
    id: str
    code: str | None
    child_id: str
    worksheet_id: str
    status: str
    worksheet_title: str
    topic: str
    section: str
    printed_at: str | None
    scanned_at: str | None
    graded_at: str | None


def _child_out(c: Child) -> ChildOut:
    return ChildOut(id=c.id, name=c.name, grade=c.grade, has_pin=bool(c.pin_hash))


@router.post("/children", response_model=ChildOut)
async def create_child(body: ChildIn, session: AsyncSession = Depends(get_session)):
    child = Child(name=body.name, grade=body.grade,
                  pin_hash=hash_pin(body.pin) if body.pin else None)
    session.add(child)
    await session.commit()
    return _child_out(child)


@router.get("/children", response_model=list[ChildOut])
async def list_children(session: AsyncSession = Depends(get_session)):
    return [_child_out(c) for c in (await session.exec(select(Child))).all()]


@router.post("/children/{child_id}/verify-pin", response_model=PinResult)
async def verify_child_pin(child_id: str, body: PinIn,
                           session: AsyncSession = Depends(get_session)) -> PinResult:
    child = (await session.exec(select(Child).where(Child.id == child_id))).first()
    if child is None:
        raise HTTPException(status_code=404, detail="child not found")
    return PinResult(ok=verify_pin(body.pin, child.pin_hash))


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


@router.get("/children/{child_id}/attempts", response_model=list[AttemptOut])
async def list_child_attempts(child_id: str, session: AsyncSession = Depends(get_session)):
    rows = (await session.exec(
        select(Attempt, Worksheet, Skill)
        .where(Attempt.child_id == child_id)
        .join(Worksheet, Worksheet.id == Attempt.worksheet_id)
        .join(Skill, Skill.id == Worksheet.skill_id)
        .order_by(Attempt.created_at.desc())
    )).all()
    return [AttemptOut(
        id=a.id, code=a.code, child_id=a.child_id, worksheet_id=a.worksheet_id, status=a.status,
        worksheet_title=w.title, topic=s.topic, section=s.label,
        printed_at=a.printed_at.isoformat() if a.printed_at else None,
        scanned_at=a.scanned_at.isoformat() if a.scanned_at else None,
        graded_at=a.graded_at.isoformat() if a.graded_at else None,
    ) for a, w, s in rows]


@router.get("/attempts/{attempt_id}/print")
async def download_print(attempt_id: str, session: AsyncSession = Depends(get_session),
                         store: ObjectStore = Depends(get_store)):
    attempt = (await session.exec(select(Attempt).where(Attempt.id == attempt_id))).first()
    if attempt is None or attempt.print_pdf_r2_key is None:
        raise HTTPException(status_code=404, detail="attempt or print not found")
    pdf = await asyncio.to_thread(store.get, attempt.print_pdf_r2_key)
    return Response(content=pdf, media_type="application/pdf")
