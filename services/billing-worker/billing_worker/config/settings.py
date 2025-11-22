from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def find_env_file() -> str:
    env_file = ".env" if Path("/.dockerenv").exists() else ".env.local"

    current_path = Path.cwd()

    for path in [current_path] + list(current_path.parents):
        env_path = path / env_file
        if env_path.exists():
            return str(env_path)

    return env_file


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+psycopg2://app:app@db:5432/rental"

    # External services
    external_base: str = "http://external-stubs:3629"
    http_timeout_sec: float = 1.5

    # Billing settings
    billing_tick_sec: int = 30
    r_buyout: int = 5000

    # Debt retry settings
    debt_charge_step: int = 100
    debt_retry_base_sec: int = 60
    debt_retry_max_sec: int = 3600
