from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.models import Problem, Skill, Worksheet

router = APIRouter(prefix="/api")


@router.get("/skills")
async def list_skills(grade: int | None = None, session: AsyncSession = Depends(get_session)):
    stmt = select(Skill)
    if grade is not None:
        stmt = stmt.where(Skill.grade == grade)
    return (await session.exec(stmt)).all()


@router.get("/skills/{skill_id}/worksheets")
async def list_worksheets(skill_id: str, session: AsyncSession = Depends(get_session)):
    return (await session.exec(select(Worksheet).where(Worksheet.skill_id == skill_id))).all()


@router.get("/worksheets/{worksheet_id}")
async def worksheet_detail(worksheet_id: str, session: AsyncSession = Depends(get_session)):
    ws = (await session.exec(select(Worksheet).where(Worksheet.id == worksheet_id))).first()
    if ws is None:
        raise HTTPException(status_code=404, detail="worksheet not found")
    problems = (await session.exec(
        select(Problem).where(Problem.worksheet_id == worksheet_id).order_by(Problem.number)
    )).all()
    return {**ws.model_dump(), "problems": [p.model_dump() for p in problems]}
