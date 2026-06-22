"""Shared Google Cloud auth + client construction for the Gemini providers.

Vertex needs credentials. Two supported sources, in priority order:
  1. GCP_SERVICE_ACCOUNT_KEY — the full service-account JSON, inline (single line).
  2. Application Default Credentials — e.g. GOOGLE_APPLICATION_CREDENTIALS file path
     or `gcloud auth application-default login` (used when the inline key is blank).
"""

import json

from google import genai

from app.config import settings

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def vertex_credentials():
    """Credentials from the inline service-account key, or None to fall back to ADC."""
    raw = (settings.gcp_service_account_key or "").strip()
    if not raw:
        return None
    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_info(
        json.loads(raw), scopes=_SCOPES
    )


def make_genai_client(*, api_key: str = "", use_vertex: bool = False,
                      project: str | None = None, location: str | None = None):
    """Build a google-genai client. Vertex mode prefers the inline SA key, then ADC."""
    if not use_vertex:
        return genai.Client(api_key=api_key)
    kwargs = {
        "vertexai": True,
        "project": project or settings.gcp_project_id or None,
        "location": location,
    }
    creds = vertex_credentials()
    if creds is not None:
        kwargs["credentials"] = creds
    return genai.Client(**kwargs)
