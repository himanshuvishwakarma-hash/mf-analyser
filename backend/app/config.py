"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Environment
    environment: str = "development"
    log_level: str = "INFO"

    # Database / cache
    database_url: str = "postgresql+psycopg://mfa:mfa_password@postgres:5432/mf_analyser"
    redis_url: str = "redis://redis:6379/0"

    # MFApi.in
    mfapi_base_url: str = "https://api.mfapi.in"
    mfapi_request_delay_ms: int = 100

    # Scoring
    risk_free_rate: float = 0.08
    min_nav_history_months: int = 36

    # Monte Carlo
    monte_carlo_simulations: int = 10000

    # Celery
    celery_schedule_hour: int = 23

    # CORS
    api_cors_origins: str = "http://localhost:5173"

    # Sentry
    sentry_dsn: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
