from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ORVYN API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True

    api_v1_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:3000"

    database_url: str = "sqlite+aiosqlite:///./orvyn.db"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.6-flash"
    gemini_fallback_model: str = "gemini-3.5-flash-lite"

    openai_api_key: str | None = None
    gemini_api_key: str | None = None

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