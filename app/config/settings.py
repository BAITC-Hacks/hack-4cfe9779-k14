from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Chat Service API"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str
    ekt_api_base_url: str = "https://ekt.kz/api/"
    ekt_api_username: str | None = None
    ekt_api_password: SecretStr | None = None
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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
