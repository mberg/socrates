import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
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
        ws = Worksheet(skill_id=skill.id, source="k5", title="W", problem_count=2, pdf_sha256="sha")
        s.add(ws); await s.flush()
        s.add(Problem(worksheet_id=ws.id, number=1, prompt="2+2", correct_answer="4"))
        s.add(Problem(worksheet_id=ws.id, number=2, prompt="3+3", correct_answer="6"))
        child = Child(name="Ada", grade=5); s.add(child); await s.flush()
        attempt = Attempt(child_id=child.id, worksheet_id=ws.id); s.add(attempt); await s.commit()
        child_id, attempt_id = child.id, attempt.id

    async def _sess():
        async with factory() as s:
            yield s

    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="4", confidence=0.95),
        ProblemRead(number=2, read_answer="7", confidence=0.95),
    ]))
    app = create_app()
    app.dependency_overrides[get_session] = _sess
    app.dependency_overrides[get_store] = lambda: InMemoryObjectStore()
    app.dependency_overrides[get_vision] = lambda: vision
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c._child_id, c._attempt_id = child_id, attempt_id
        c._app = app
        yield c
    await engine.dispose()


async def test_upload_grades_whole_sheet(client):
    files = {"file": ("sheet.jpg", b"img-bytes", "image/jpeg")}
    resp = await client.post(
        f"/api/children/{client._child_id}/attempts/{client._attempt_id}/submissions", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["score_total"] == 2 and body["score_correct"] == 1
    assert {r["number"] for r in body["results"]} == {1, 2}


async def test_results_endpoint_returns_latest(client):
    files = {"file": ("sheet.jpg", b"img-bytes", "image/jpeg")}
    await client.post(
        f"/api/children/{client._child_id}/attempts/{client._attempt_id}/submissions", files=files)
    resp = await client.get(f"/api/attempts/{client._attempt_id}/results")
    assert resp.status_code == 200
    assert resp.json()["score_total"] == 2


async def test_unknown_attempt_404(client):
    files = {"file": ("sheet.jpg", b"img", "image/jpeg")}
    resp = await client.post(
        f"/api/children/{client._child_id}/attempts/nope/submissions", files=files)
    assert resp.status_code == 404


async def test_results_before_grading_404(client):
    resp = await client.get(f"/api/attempts/{client._attempt_id}/results")
    assert resp.status_code == 404


async def test_code_mismatch_grades_anyway_and_flags(client):
    """The printed-code cross-check is advisory: a mismatch grades the sheet (200)
    but reports identity_ok=False rather than blocking."""
    mismatch_vision = FakeVision(VisionRead(printed_id="ZZZZZ", problems=[
        ProblemRead(number=1, read_answer="4", confidence=0.95),
        ProblemRead(number=2, read_answer="6", confidence=0.95),
    ]))
    client._app.dependency_overrides[get_vision] = lambda: mismatch_vision
    files = {"file": ("sheet.jpg", b"img-bytes", "image/jpeg")}
    post_resp = await client.post(
        f"/api/children/{client._child_id}/attempts/{client._attempt_id}/submissions", files=files)
    assert post_resp.status_code == 200
    assert post_resp.json()["identity_ok"] is False
    assert post_resp.json()["score_total"] == 2

    get_resp = await client.get(f"/api/attempts/{client._attempt_id}/results")
    assert get_resp.status_code == 200


async def test_ai_fallback_form_toggle_changes_scoring(client):
    """A code-decidable numeric mismatch (#1 read '5' vs correct '4') is wrong by
    default, but with ai_fallback=true the (equivalent=True) Gemini check marks it
    right — proving the form toggle reaches the service."""
    vision = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="5", confidence=0.95),
        ProblemRead(number=2, read_answer="6", confidence=0.95),
    ]), equivalent=True)
    client._app.dependency_overrides[get_vision] = lambda: vision
    files = {"file": ("sheet.jpg", b"img-bytes", "image/jpeg")}

    default = await client.post(
        f"/api/children/{client._child_id}/attempts/{client._attempt_id}/submissions", files=files)
    assert default.status_code == 200
    assert default.json()["score_correct"] == 1  # #1 wrong by code, no AI call

    forced = await client.post(
        f"/api/children/{client._child_id}/attempts/{client._attempt_id}/submissions",
        files=files, data={"ai_fallback": "true"})
    assert forced.status_code == 200
    assert forced.json()["score_correct"] == 2  # #1 rescued by forced Gemini check


async def test_latest_graded_wins_across_two_submissions(client):
    """When two graded submissions exist, get_results returns the more recent one."""
    files = {"file": ("sheet.jpg", b"img-bytes", "image/jpeg")}

    # First submission: 1/2 correct (answer to #2 is wrong: "7" vs correct "6").
    vision_first = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="4", confidence=0.95),
        ProblemRead(number=2, read_answer="7", confidence=0.95),
    ]))
    client._app.dependency_overrides[get_vision] = lambda: vision_first
    r1 = await client.post(
        f"/api/children/{client._child_id}/attempts/{client._attempt_id}/submissions", files=files)
    assert r1.status_code == 200
    assert r1.json()["score_correct"] == 1

    # Second submission: 2/2 correct.
    vision_second = FakeVision(VisionRead(printed_id=None, problems=[
        ProblemRead(number=1, read_answer="4", confidence=0.95),
        ProblemRead(number=2, read_answer="6", confidence=0.95),
    ]))
    client._app.dependency_overrides[get_vision] = lambda: vision_second
    r2 = await client.post(
        f"/api/children/{client._child_id}/attempts/{client._attempt_id}/submissions", files=files)
    assert r2.status_code == 200
    assert r2.json()["score_correct"] == 2

    # GET /results must return the second (latest graded) submission.
    get_resp = await client.get(f"/api/attempts/{client._attempt_id}/results")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["score_correct"] == 2
    assert body["score_total"] == 2
    assert body["submission_id"] == r2.json()["submission_id"]
