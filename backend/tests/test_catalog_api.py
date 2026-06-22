import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.main import create_app
from app.models import Problem, Skill, Worksheet


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        skill = Skill(grade=5, topic="place-value-rounding", skill_key="place-value-5-digit", label="Build a 5-digit number")
        s.add(skill); await s.flush()
        ws = Worksheet(skill_id=skill.id, source="k5", variant="a", title="Build a 5-digit number",
                       problem_count=1, pdf_sha256="sha-a")
        s.add(ws); await s.flush()
        s.add(Problem(worksheet_id=ws.id, number=1, prompt="30,000 + 100 + 4", correct_answer="30,104"))
        await s.commit()

    async def _override():
        async with factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def test_list_skills_by_grade(client):
    resp = await client.get("/api/skills?grade=5")
    assert resp.status_code == 200
    assert resp.json()[0]["skill_key"] == "place-value-5-digit"


async def test_worksheet_detail_includes_problems(client):
    skills = (await client.get("/api/skills?grade=5")).json()
    wss = (await client.get(f"/api/skills/{skills[0]['id']}/worksheets")).json()
    detail = (await client.get(f"/api/worksheets/{wss[0]['id']}")).json()
    assert detail["title"] == "Build a 5-digit number"
    assert detail["problems"][0]["correct_answer"] == "30,104"
