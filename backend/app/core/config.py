from functools import lru_cache

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    app_name: str = "ORVYN API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True

    api_v1_prefix: str = "/api/v1"

    frontend_url: str = (
        "http://localhost:3000"
    )

    database_url: str = (
        "sqlite+aiosqlite:///./orvyn.db"
    )

    jwt_secret: str

    jwt_algorithm: str = "HS256"

    access_token_expire_minutes: int = 60

    access_token_cookie_name: str = (
        "orvyn_access_token"
    )

    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    llm_provider: str = "gemini"

    llm_model: str = (
        "gemini-3.6-flash"
    )

    gemini_fallback_model: str = (
        "gemini-3.5-flash-lite"
    )

    openai_api_key: str | None = None
    gemini_api_key: str | None = None

    upload_dir: str = (
        "storage/uploads"
    )

    max_upload_size_mb: int = 10

    max_attachments_per_message: int = 5
        # RAG configuration
    embedding_model: str = (
        "gemini-embedding-001"
    )

    embedding_dimensions: int = 768

    rag_chunk_size: int = 1200

    rag_chunk_overlap: int = 200

    rag_top_k: int = 5

    rag_min_similarity: float = 0.25

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()