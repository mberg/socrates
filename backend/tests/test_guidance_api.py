import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.guidance import get_tutor
from app.db import get_session
from app.main import create_app
from app.models import (Attempt, Child, Problem, ProblemResult, Submission, Worksheet)
from app.tutor.base import FakeTutor


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        ws = Worksheet(skill_id="sk", source="k5", title="W", problem_count=1,
                       pdf_sha256="sha", worked_example="3 x 4 = 12")
        s.add(ws); await s.flush()
        prob = Problem(worksheet_id=ws.id, number=3, prompt="3 x 4", correct_answer="12")
        s.add(prob); await s.flush()
        child = Child(name="Ada", grade=3); s.add(child); await s.flush()
        att = Attempt(child_id=child.id, worksheet_id=ws.id); s.add(att); await s.flush()
        sub = Submission(attempt_id=att.id, photo_r2_key="k"); s.add(sub); await s.flush()
        s.add(ProblemResult(submission_id=sub.id, problem_id=prob.id, read_answer="7",
                            is_correct=False, confidence=0.9, match_method="normalized"))
        await s.commit()
        ids = (child.id, att.id, prob.id)

    async def _sess():
        async with factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _sess
    app.dependency_overrides[get_tutor] = lambda: FakeTutor()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c._ids = ids
        yield c
    await engine.dispose()


async def test_start_returns_tier1_opening_turn(client):
    child_id, att_id, prob_id = client._ids
    r = await client.post(f"/api/children/{child_id}/attempts/{att_id}/problems/{prob_id}/guidance")
    assert r.status_code == 200
    body = r.json()
    assert body["max_tier_reached"] == 1
    assert body["problem_number"] == 3
    assert len(body["turns"]) == 1 and body["turns"][0]["role"] == "tutor"
    assert "12" not in body["turns"][0]["text"]  # answer not revealed at Tier 1


async def test_advance_to_tier3_reveals_answer(client):
    child_id, att_id, prob_id = client._ids
    sid = (await client.post(
        f"/api/children/{child_id}/attempts/{att_id}/problems/{prob_id}/guidance")).json()["id"]
    await client.post(f"/api/guidance/{sid}/turns", json={"advance": True})
    body = (await client.post(f"/api/guidance/{sid}/turns", json={"advance": True})).json()
    assert body["max_tier_reached"] == 3
    assert "12" in body["turns"][-1]["text"]  # Tier 3 reveals


async def test_reveal_jumps_straight_to_tier3(client):
    child_id, att_id, prob_id = client._ids
    sid = (await client.post(
        f"/api/children/{child_id}/attempts/{att_id}/problems/{prob_id}/guidance")).json()["id"]
    # One "show me the answer" tap from Tier 1 jumps directly to Tier 3 and reveals.
    body = (await client.post(f"/api/guidance/{sid}/turns", json={"reveal": True})).json()
    assert body["max_tier_reached"] == 3
    assert "12" in body["turns"][-1]["text"]


async def test_child_turn_records_input_source(client):
    child_id, att_id, prob_id = client._ids
    sid = (await client.post(
        f"/api/children/{child_id}/attempts/{att_id}/problems/{prob_id}/guidance")).json()["id"]
    body = (await client.post(f"/api/guidance/{sid}/turns",
                              json={"text": "I added them", "input_source": "voice"})).json()
    child_turns = [t for t in body["turns"] if t["role"] == "child"]
    assert child_turns and child_turns[-1]["input_source"] == "voice"


async def test_resolve_marks_session(client):
    child_id, att_id, prob_id = client._ids
    sid = (await client.post(
        f"/api/children/{child_id}/attempts/{att_id}/problems/{prob_id}/guidance")).json()["id"]
    body = (await client.post(f"/api/guidance/{sid}/resolve")).json()
    assert body["resolved"] is True


async def test_start_is_idempotent_while_open(client):
    child_id, att_id, prob_id = client._ids
    a = (await client.post(f"/api/children/{child_id}/attempts/{att_id}/problems/{prob_id}/guidance")).json()
    b = (await client.post(f"/api/children/{child_id}/attempts/{att_id}/problems/{prob_id}/guidance")).json()
    assert a["id"] == b["id"]  # same open session reused, not a second opening turn storm
