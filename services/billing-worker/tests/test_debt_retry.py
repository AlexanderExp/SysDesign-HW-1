from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from billing_worker.config.settings import settings
from billing_worker.db.models import Base, Debt, Rental
from billing_worker.db.repositories.debt import DebtRepository
from billing_worker.db.repositories.payment import PaymentRepository
from billing_worker.db.repositories.rental import RentalRepository
from billing_worker.services.debt import DebtService
from billing_worker.services.payment import PaymentService


@pytest.fixture
def sqlite_session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
    Base.metadata.create_all(engine)

    session = Session()
    yield session
    session.close()


@pytest.fixture
def repositories(sqlite_session):
    rental_repo = RentalRepository(sqlite_session)
    debt_repo = DebtRepository(sqlite_session)
    payment_repo = PaymentRepository(sqlite_session)
    return rental_repo, debt_repo, payment_repo


@pytest.fixture
def services(repositories):
    rental_repo, debt_repo, payment_repo = repositories
    payment_service = PaymentService(payment_repo, rental_repo)
    debt_service = DebtService(debt_repo, payment_repo, rental_repo)
    return payment_service, debt_service


def test_due_amount_calculation(repositories):
    rental_repo, _, _ = repositories

    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=90)  # 1.5 minutes

    rental = Rental(
        id="test",
        user_id="user1",
        powerbank_id="pb1",
        price_per_hour=60,
        free_period_min=0,
        deposit=100,
        status="ACTIVE",
        total_amount=0,
        started_at=start,
    )

    # 60rub/hour for 90 seconds should be 1rub
    due_amount = rental_repo.calculate_due_amount(rental, now)
    assert due_amount == 1


def test_backoff_calculation(services):
    _, debt_service = services

    # Mock settings for test
    original_base = settings.debt_retry_base_sec
    original_max = settings.debt_retry_max_sec

    settings.debt_retry_base_sec = 60
    settings.debt_retry_max_sec = 600

    try:
        assert debt_service.calculate_backoff_seconds(0) == 60
        assert debt_service.calculate_backoff_seconds(1) == 120
        assert debt_service.calculate_backoff_seconds(4) == 600  # capped
    finally:
        settings.debt_retry_base_sec = original_base
        settings.debt_retry_max_sec = original_max


def test_historical_debt_success(sqlite_session, services, monkeypatch):
    payment_service, debt_service = services

    now = datetime.now(timezone.utc)

    # Create test data
    rental = Rental(
        id="r1",
        user_id="u1",
        powerbank_id="pb",
        price_per_hour=60,
        free_period_min=0,
        deposit=100,
        status="ACTIVE",
        total_amount=0,
        started_at=now - timedelta(hours=1),
    )
    sqlite_session.add(rental)

    debt = Debt(
        rental_id="r1",
        amount_total=250,
        updated_at=now - timedelta(hours=1),
        attempts=2,
        last_attempt_at=now - timedelta(hours=2),
    )
    sqlite_session.add(debt)
    sqlite_session.commit()

    # Mock external client to always succeed
    mock_client = Mock()
    mock_client.clear_money_for_order.return_value = (True, None)
    monkeypatch.setattr("billing_worker.services.debt.external_client", mock_client)

    # Mock settings
    original_step = settings.debt_charge_step
    settings.debt_charge_step = 100

    try:
        # Test debt collection
        charged, debt_delta = debt_service.try_collect_historical_debt("r1", now)
        sqlite_session.commit()

        assert charged == 100
        assert debt_delta == -100

        # Verify debt was reduced
        updated_debt = sqlite_session.get(Debt, "r1")
        assert updated_debt.amount_total == 150
        assert updated_debt.attempts == 0
        assert updated_debt.last_attempt_at is not None

        # Verify rental total was updated
        updated_rental = sqlite_session.get(Rental, "r1")
        assert updated_rental.total_amount == 100

    finally:
        settings.debt_charge_step = original_step


def test_historical_debt_failure(sqlite_session, services, monkeypatch):
    """Test failed historical debt collection."""
    payment_service, debt_service = services

    now = datetime.now(timezone.utc)

    # Create test data
    rental = Rental(
        id="r2",
        user_id="u2",
        powerbank_id="pb",
        price_per_hour=60,
        free_period_min=0,
        deposit=100,
        status="ACTIVE",
        total_amount=0,
        started_at=now - timedelta(hours=1),
    )
    sqlite_session.add(rental)

    debt = Debt(
        rental_id="r2",
        amount_total=70,
        updated_at=now - timedelta(hours=1),
        attempts=0,
        last_attempt_at=now - timedelta(hours=2),
    )
    sqlite_session.add(debt)
    sqlite_session.commit()

    # Mock external client to always fail
    mock_client = Mock()
    mock_client.clear_money_for_order.return_value = (False, "Payment failed")
    monkeypatch.setattr("billing_worker.services.debt.external_client", mock_client)

    # Mock settings
    original_step = settings.debt_charge_step
    settings.debt_charge_step = 100  # Will try to charge 70 (min of debt and step)

    try:
        # Test debt collection
        charged, debt_delta = debt_service.try_collect_historical_debt("r2", now)
        sqlite_session.commit()

        assert charged == 0
        assert debt_delta == 0

        # Verify debt unchanged but attempts incremented
        updated_debt = sqlite_session.get(Debt, "r2")
        assert updated_debt.amount_total == 70
        assert updated_debt.attempts == 1
        assert updated_debt.last_attempt_at is not None

        # Verify rental total unchanged
        updated_rental = sqlite_session.get(Rental, "r2")
        assert updated_rental.total_amount == 0

    finally:
        settings.debt_charge_step = original_step
