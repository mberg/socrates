import fitz
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.children import get_store
from app.db import get_session
from app.main import create_app
from app.models import Skill, Worksheet
from app.storage import InMemoryObjectStore


def _two_page_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "WORKSHEET")
    doc.new_page().insert_text((72, 72), "ANSWER KEY")
    return doc.tobytes()


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    store = InMemoryObjectStore()
    store.put("worksheets/sha7.pdf", _two_page_pdf(), "application/pdf")
    async with factory() as s:
        skill = Skill(grade=5, topic="t", skill_key="k", label="L"); s.add(skill); await s.flush()
        ws = Worksheet(skill_id=skill.id, source="k5", title="W", problem_count=1,
                       pdf_sha256="sha7", source_pdf_r2_key="worksheets/sha7.pdf")
        s.add(ws); await s.commit()
        ws_id = ws.id

    async def _sess():
        async with factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _sess
    app.dependency_overrides[get_store] = lambda: store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c._ws_id = ws_id  # stash for tests
        yield c
    await engine.dispose()


async def test_create_child_and_attempt_and_download_print(client):
    child = (await client.post("/api/children", json={"name": "Ada", "grade": 5})).json()
    assert child["grade"] == 5

    resp = await client.post(f"/api/children/{child['id']}/attempts", json={"worksheet_id": client._ws_id})
    assert resp.status_code == 200
    attempt = resp.json()
    assert attempt["status"] == "printed"
    assert attempt["print_pdf_r2_key"] == f"prints/{attempt['id']}.pdf"

    pdf = await client.get(f"/api/attempts/{attempt['id']}/print")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    doc = fitz.open(stream=pdf.content, filetype="pdf")
    assert doc.page_count == 1
    assert "ANSWER KEY" not in doc[0].get_text()


async def test_attempt_unknown_worksheet_404(client):
    child = (await client.post("/api/children", json={"name": "B", "grade": 3})).json()
    resp = await client.post(f"/api/children/{child['id']}/attempts", json={"worksheet_id": "missing"})
    assert resp.status_code == 404
