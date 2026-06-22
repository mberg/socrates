from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./socrates.db"

    # Gemini extraction model. Vertex mode uses Application Default Credentials
    # (set GOOGLE_APPLICATION_CREDENTIALS to the service-account JSON path).
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_api_key: str = ""
    gemini_use_vertex: bool = False
    gemini_vertex_project: str = ""
    gemini_vertex_location: str = ""

    # Inline service-account JSON (alternative to GOOGLE_APPLICATION_CREDENTIALS file
    # path). When set, it authenticates the Vertex client directly. gcp_project_id
    # overrides gemini_vertex_project when provided.
    gcp_project_id: str = ""
    gcp_service_account_key: str = ""

    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "socrates"


settings = Settings()
