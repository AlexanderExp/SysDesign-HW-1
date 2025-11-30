from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from shared.db.models import Base
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from rental_core.db.repositories.debt import DebtRepository
from rental_core.db.repositories.quote import QuoteRepository


def setup_sqlite():
    eng = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    Session = sessionmaker(
        bind=eng, autoflush=False, autocommit=False, expire_on_commit=False, future=True
    )
    return eng, Session


def test_quotes_lifecycle():
    eng, Session = setup_sqlite()
    now = datetime.now(timezone.utc)

    with Session() as s:
        quote_repo = QuoteRepository(s)
        quote_repo.create_quote(
            quote_id="q1",
            user_id="u1",
            station_id="st1",
            price_per_hour=60,
            free_period_min=0,
            deposit=300,
            expires_at=now + timedelta(seconds=60),
            created_at=now,
        )
        s.commit()

    with Session() as s:
        quote_repo = QuoteRepository(s)
        q = quote_repo.get_quote("q1")
        assert q is not None
        assert q.user_id == "u1"
        assert q.station_id == "st1"

    with Session() as s:
        quote_repo = QuoteRepository(s)
        quote_repo.delete_quote("q1")
        s.commit()

    with Session() as s:
        quote_repo = QuoteRepository(s)
        q = quote_repo.get_quote("q1")
        assert q is None


def test_attach_deposit_debt():
    eng, Session = setup_sqlite()
    now = datetime.now(timezone.utc)

    with Session() as s:
        debt_repo = DebtRepository(s)
        debt_repo.attach_debt("r1", 200, now)
        s.commit()

    with eng.begin() as conn:
        row = conn.execute(
            text("SELECT rental_id, amount_total FROM debts WHERE rental_id='r1'")
        ).first()
        assert row is not None
        assert row.amount_total == 200

    with Session() as s:
        debt_repo = DebtRepository(s)
        debt_repo.attach_debt("r1", 50, now)
        s.commit()

    with eng.begin() as conn:
        row = conn.execute(
            text("SELECT rental_id, amount_total FROM debts WHERE rental_id='r1'")
        ).first()
        assert row.amount_total == 250


def test_debt_repository_operations():
    eng, Session = setup_sqlite()

    with Session() as s:
        debt_repo = DebtRepository(s)
        debt_repo.add_debt("r1", 100)
        s.commit()

        amount = debt_repo.get_amount("r1")
        assert amount == 100

        debt = debt_repo.get_by_rental_id("r1")
        assert debt is not None
        assert debt.amount_total == 100

        success = debt_repo.reduce_debt("r1", 30)
        assert success is True
        s.commit()

        amount = debt_repo.get_amount("r1")
        assert amount == 70

        success = debt_repo.reduce_debt("r1", 100)
        assert success is False

        debt_repo.increment_attempts("r1")
        s.commit()

        debt = debt_repo.get_by_rental_id("r1")
        assert debt.attempts == 1
        assert debt.last_attempt_at is not None


def test_quote_service_integration():
    eng, Session = setup_sqlite()

    mock_external_client = Mock()
    mock_external_client.get_station_data.return_value = Mock(tariff_id="tariff1")
    mock_external_client.get_tariff.return_value = Mock(
        price_per_hour=60, free_period_min=0, default_deposit=300
    )
    mock_external_client.get_user_profile.return_value = Mock(trusted=False)

    from rental_core.schemas import QuoteRequest
    from rental_core.services.quote import QuoteService

    with Session() as s:
        quote_repo = QuoteRepository(s)
        quote_service = QuoteService(quote_repo, mock_external_client)

        request = QuoteRequest(user_id="u1", station_id="st1")
        response = quote_service.create_quote(request)

        assert response.quote_id is not None
        assert response.user_id == "u1"
        assert response.station_id == "st1"
        assert response.price_per_hour == 60
        assert response.deposit == 300
        s.commit()

        quote_data = quote_service.get_and_validate_quote(response.quote_id)
        assert quote_data.id == response.quote_id
        assert quote_data.user_id == "u1"

        quote_service.consume_quote(response.quote_id)
        s.commit()

        quote = quote_repo.get_quote(response.quote_id)
        assert quote is None
