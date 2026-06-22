import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.children import get_store
from app.api.grading import get_vision
from app.db import get_session
from app.grading.vision import FakeVision, ProblemRead, VisionRead
from app.main import create_app
from app.models import Attempt, Child, Problem, Skill, Worksheet
from app.storage import InMemoryObjectStore


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        skill = Skill(grade=5, topic="t", skill_key="k", label="L"); s.add(skill); await s.flush()
        ws = Worksheet(skill_id=skill.id, source="k5", title="W", problem_count=3, pdf_sha256="sha")
        s.add(ws); await s.flush()
        s.add(Problem(worksheet_id=ws.id, number=1, prompt="2+2", correct_answer="4"))
        s.add(Problem(worksheet_id=ws.id, number=2, prompt="3+3", correct_answer="6"))
        s.add(Problem(worksheet_id=ws.id, number=3, prompt="5+5", correct_answer="10"))
        child = Child(name="Ada", grade=5); s.add(child); await s.flush()
        attempt = Attempt(child_id=child.id, worksheet_id=ws.id); s.add(attempt); await s.commit()
        child_id, attempt_id = child.id, attempt.id

    async def _sess():
        async with factory() as s:
            yield s

    # #1 correct, #2 attempted-wrong, #3 blank
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="4", confidence=0.95),
        ProblemRead(number=2, read_answer="7", confidence=0.95),
        ProblemRead(number=3, read_answer=None, confidence=0.0),
    ]))
    app = create_app()
    app.dependency_overrides[get_session] = _sess
    app.dependency_overrides[get_store] = lambda: InMemoryObjectStore()
    app.dependency_overrides[get_vision] = lambda: vision
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c._child_id, c._attempt_id = child_id, attempt_id
        yield c
    await engine.dispose()


def _by_num(body):
    return {r["number"]: r for r in body["results"]}


async def test_correct_answer_only_on_attempted_wrong(client):
    files = {"file": ("s.jpg", b"img", "image/jpeg")}
    body = (await client.post(
        f"/api/children/{client._child_id}/attempts/{client._attempt_id}/submissions", files=files)).json()
    n = _by_num(body)
    assert n[1]["correct_answer"] is None     # correct → not revealed
    assert n[2]["correct_answer"] == "6"      # attempted-wrong → revealed
    assert n[3]["correct_answer"] is None     # blank → never revealed


async def test_results_endpoint_applies_same_rule(client):
    files = {"file": ("s.jpg", b"img", "image/jpeg")}
    await client.post(
        f"/api/children/{client._child_id}/attempts/{client._attempt_id}/submissions", files=files)
    n = _by_num((await client.get(f"/api/attempts/{client._attempt_id}/results")).json())
    assert n[1]["correct_answer"] is None
    assert n[2]["correct_answer"] == "6"
    assert n[3]["correct_answer"] is None
