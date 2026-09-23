from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Chat Service API"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str
    cors_allowed_origins: str
    ekt_api_base_url: str = "https://ekt.kz/api/"
    ekt_api_username: str | None = None
    ekt_api_password: SecretStr | None = None
    ekt_read_retry_count: int = Field(default=1, ge=0, le=3)
    ekt_retry_backoff_seconds: float = Field(default=0.05, ge=0, le=5)
    llm_api_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str = ""
    llm_temperature: float = 0.0
    llm_timeout_seconds: float = 15.0
    llm_history_message_limit: int = 12
    pending_offer_ttl_seconds: int = 300
    idempotency_key_ttl_seconds: int = 86400
    attachment_max_bytes: int = 10 * 1024 * 1024
    attachment_max_xlsx_sheets: int = 20
    attachment_max_xlsx_rows: int = 10000
    attachment_max_xlsx_columns: int = 100
    attachment_llm_max_chars: int = 12000
    attachment_ttl_seconds: int = Field(default=86400, ge=60, le=2_592_000)
    cleanup_batch_size: int = Field(default=1000, ge=1, le=10_000)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(origin.strip().rstrip("/") for origin in self.cors_allowed_origins.split(",") if origin.strip())
        )

    @model_validator(mode="after")
    def validate_cors_origins(self) -> "Settings":
        origins = self.cors_origins
        if not origins:
            raise ValueError("CORS_ALLOWED_ORIGINS must contain at least one origin")
        if "*" in origins:
            raise ValueError("Wildcard CORS origins are not allowed")
        if any(not origin.startswith(("http://", "https://")) for origin in origins):
            raise ValueError("CORS origins must use http:// or https://")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
