import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.main import create_app


@pytest.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _sess():
        async with factory() as s:
            yield s

    app = create_app()
    app.dependency_overrides[get_session] = _sess
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await engine.dispose()


async def test_create_child_without_pin_has_no_pin_and_no_hash_leak(client):
    r = await client.post("/api/children", json={"name": "Ada", "grade": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["has_pin"] is False
    assert "pin_hash" not in body and "pin" not in body


async def test_create_with_pin_then_verify(client):
    cid = (await client.post("/api/children", json={"name": "B", "grade": 3, "pin": "1234"})).json()["id"]
    assert (await client.post(f"/api/children/{cid}/verify-pin", json={"pin": "1234"})).json()["ok"] is True
    assert (await client.post(f"/api/children/{cid}/verify-pin", json={"pin": "9999"})).json()["ok"] is False


async def test_verify_open_when_no_pin(client):
    cid = (await client.post("/api/children", json={"name": "C", "grade": 5})).json()["id"]
    assert (await client.post(f"/api/children/{cid}/verify-pin", json={"pin": "whatever"})).json()["ok"] is True


async def test_list_children_returns_has_pin_not_hash(client):
    await client.post("/api/children", json={"name": "D", "grade": 5, "pin": "1111"})
    row = (await client.get("/api/children")).json()[0]
    assert set(row) == {"id", "name", "grade", "has_pin"}
    assert row["has_pin"] is True
