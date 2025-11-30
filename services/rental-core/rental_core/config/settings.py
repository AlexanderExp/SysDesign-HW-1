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

    # Database: основная БД rental-core
    database_url: str = "postgresql+psycopg2://app:app@db:5432/rental"

    # Database: БД для долгов и платежей
    billing_database_url: str = "postgresql+psycopg2://app:app@db-billing:5432/billing"
    # External services
    external_base: str = "http://external-stubs:3629"
    http_timeout_sec: float = 1.5

    # Circuit Breaker settings
    cb_station_fail_max: int = 5  # Max failures for station operations
    cb_station_reset_timeout: int = 30  # Reset timeout in seconds
    cb_payment_fail_max: int = 3  # Max failures for payment operations
    cb_payment_reset_timeout: int = 60  # Reset timeout in seconds
    cb_profile_fail_max: int = 10  # Max failures for profile operations
    cb_profile_reset_timeout: int = 15  # Reset timeout in seconds

    # Tariffs cache
    tariff_ttl_sec: int = 600  # 10 minutes

    # Pricing
    magic_low_banks: int = 2  # threshold for "low banks"
    last_banks_increase: float = 1.5  # fallback if no configs
    greedy_price_mult: float = 1.2  # multiplier for users fallback
    free_period_min_subscriber: int = 30  # minimum for subscribers
