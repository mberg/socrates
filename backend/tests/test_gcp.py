from app.gcp import vertex_credentials


def test_blank_key_returns_none(monkeypatch):
    monkeypatch.setattr("app.gcp.settings.gcp_service_account_key", "")
    assert vertex_credentials() is None


def test_whitespace_key_returns_none(monkeypatch):
    monkeypatch.setattr("app.gcp.settings.gcp_service_account_key", "   \n ")
    assert vertex_credentials() is None
