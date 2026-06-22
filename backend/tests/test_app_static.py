import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_still_ok(client):
    assert (await client.get("/health")).status_code == 200


async def test_dev_harness_served(client):
    r = await client.get("/dev")
    assert r.status_code == 200
    assert "Socrates" in r.text


async def test_root_serves_something(client):
    # When frontend/dist exists it serves index.html; otherwise a friendly notice.
    r = await client.get("/")
    assert r.status_code == 200
