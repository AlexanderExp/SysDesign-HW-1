import os
import time
from typing import Generator

import pytest
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for rental-core API."""
    return os.getenv("RENTAL_CORE_BASE", "http://localhost:8000")


@pytest.fixture(scope="session")
def external_base() -> str:
    """Base URL for external stubs."""
    return os.getenv("EXTERNAL_BASE", "http://localhost:3629")


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://app:app@localhost:5433/rental",
    )


@pytest.fixture(scope="session")
def billing_database_url() -> str:
    return os.getenv(
        "BILLING_DATABASE_URL",
        "postgresql+psycopg2://app:app@localhost:5434/billing",
    )


@pytest.fixture(scope="session")
def db_engine(database_url: str):
    """Create database engine."""
    engine = create_engine(database_url)
    yield engine
    engine.dispose()

@pytest.fixture(scope="session")
def billing_db_engine(billing_database_url: str):
    engine = create_engine(billing_database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    """Create database session for tests."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def billing_db_session(billing_db_engine) -> Generator[Session, None, None]:
    SessionLocal = sessionmaker(bind=billing_db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def api_client(base_url: str):
    """HTTP client for API requests."""

    class APIClient:
        def __init__(self, base_url: str):
            self.base_url = base_url.rstrip("/")
            self.session = requests.Session()
            self.session.headers.update({"Content-Type": "application/json"})

        def get(self, path: str, **kwargs):
            url = f"{self.base_url}/{path.lstrip('/')}"
            response = self.session.get(url, **kwargs)
            response.raise_for_status()
            return response.json()

        def post(self, path: str, json=None, headers=None, **kwargs):
            url = f"{self.base_url}/{path.lstrip('/')}"
            all_headers = {**self.session.headers}
            if headers:
                all_headers.update(headers)
            response = self.session.post(url, json=json, headers=all_headers, **kwargs)
            return response

    return APIClient(base_url)


@pytest.fixture
def wait_for_billing():
    """Helper to wait for billing worker to process."""

    def _wait(seconds: int = 3):
        time.sleep(seconds)

    return _wait


@pytest.fixture
def cleanup_db(db_session: Session, billing_db_session: Session):
    """Cleanup database after test."""
    db_session.execute(text("DELETE FROM rentals"))
    db_session.execute(text("DELETE FROM quotes"))
    db_session.execute(text("DELETE FROM idempotency_keys"))
    db_session.commit()

    billing_db_session.execute(text("DELETE FROM payment_attempts"))
    billing_db_session.execute(text("DELETE FROM debts"))
    billing_db_session.commit()

    yield


@pytest.fixture
def test_user_id() -> str:
    """Test user ID."""
    return "test_user_1"


@pytest.fixture
def test_station_id() -> str:
    """Test station ID."""
    return "some-station-id"


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "billing: mark test as billing-related")

from shared.db.models import Base, PaymentAttempt, Debt

@pytest.fixture(scope="session", autouse=True)
def init_billing_schema(billing_db_engine):
    """
    Гарантируем, что в billing-БД есть таблицы payment_attempts и debts
    перед запуском любых тестов.
    """
    engine = billing_db_engine

    Base.metadata.create_all(
        bind=engine,
        tables=[PaymentAttempt.__table__, Debt.__table__],
    )

    yield