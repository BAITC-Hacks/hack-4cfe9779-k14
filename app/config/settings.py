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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
