import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_root_serves_tester_html(client):
    resp = await client.get("/dev")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    assert "Socrates" in body
    assert "/submissions" in body
    assert 'capture="environment"' in body
