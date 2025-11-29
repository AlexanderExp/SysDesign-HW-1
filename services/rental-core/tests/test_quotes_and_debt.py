from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from rental_core.db.repositories.quote import QuoteRepository
from rental_core.db.repositories.debt import DebtRepository
from shared.db.models import Base


def setup_sqlite():
    eng = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    Session = sessionmaker(
        bind=eng, autoflush=False, autocommit=False, expire_on_commit=False, future=True
    )
    return eng, Session


def test_quotes_lifecycle():
    """Test quote creation, retrieval, and deletion"""
    eng, Session = setup_sqlite()
    now = datetime.now(timezone.utc)

    with Session() as s:
        # Create quote repository
        quote_repo = QuoteRepository(s)
        
        # Create a quote
        qid = "q1"
        quote_repo.create_quote(
            quote_id=qid,
            user_id="u1",
            station_id="st1",
            price_per_hour=60,
            free_period_min=0,
            deposit=300,
            expires_at=now + timedelta(seconds=60),
            created_at=now
        )
        s.commit()

    with Session() as s:
        # Load quote
        quote_repo = QuoteRepository(s)
        q = quote_repo.get_quote("q1")
        assert q is not None
        assert q.user_id == "u1"
        assert q.station_id == "st1"

    with Session() as s:
        # Delete quote
        quote_repo = QuoteRepository(s)
        quote_repo.delete_quote("q1")
        s.commit()

    with Session() as s:
        # Verify quote is deleted
        quote_repo = QuoteRepository(s)
        q = quote_repo.get_quote("q1")
        assert q is None


def test_attach_deposit_debt():
    """Test debt creation and accumulation"""
    eng, Session = setup_sqlite()
    now = datetime.now(timezone.utc)

    with Session() as s:
        # Create debt repository
        debt_repo = DebtRepository(s)
        
        # Attach initial debt
        debt_repo.attach_debt("r1", 200, now)
        s.commit()

    with eng.begin() as conn:
        row = conn.execute(
            text("SELECT rental_id, amount_total FROM debts WHERE rental_id='r1'")
        ).first()
        assert row is not None
        assert row.amount_total == 200

    # Test debt accumulation
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
    """Test various debt repository operations"""
    eng, Session = setup_sqlite()
    now = datetime.now(timezone.utc)

    with Session() as s:
        debt_repo = DebtRepository(s)
        
        # Test adding debt
        debt_repo.add_debt("r1", 100)
        s.commit()
        
        # Test getting amount
        amount = debt_repo.get_amount("r1")
        assert amount == 100
        
        # Test getting debt object
        debt = debt_repo.get_by_rental_id("r1")
        assert debt is not None
        assert debt.amount_total == 100
        
        # Test reducing debt
        success = debt_repo.reduce_debt("r1", 30)
        assert success is True
        s.commit()
        
        # Verify reduced amount
        amount = debt_repo.get_amount("r1")
        assert amount == 70
        
        # Test reducing more than available
        success = debt_repo.reduce_debt("r1", 100)
        assert success is False
        
        # Test increment attempts
        debt_repo.increment_attempts("r1")
        s.commit()
        
        debt = debt_repo.get_by_rental_id("r1")
        assert debt.attempts == 1
        assert debt.last_attempt_at is not None


def test_quote_service_integration():
    """Test quote service with mocked external dependencies"""
    eng, Session = setup_sqlite()
    
    # Mock external client
    mock_external_client = Mock()
    mock_external_client.get_station_data.return_value = Mock(tariff_id="tariff1")
    mock_external_client.get_tariff.return_value = Mock(
        price_per_hour=60,
        free_period_min=0,
        default_deposit=300
    )
    mock_external_client.get_user_profile.return_value = Mock(trusted=False)
    
    # Import QuoteService
    from rental_core.services.quote import QuoteService
    from rental_core.schemas import QuoteRequest
    
    with Session() as s:
        quote_repo = QuoteRepository(s)
        quote_service = QuoteService(quote_repo, mock_external_client)
        
        # Test quote creation
        request = QuoteRequest(user_id="u1", station_id="st1")
        response = quote_service.create_quote(request)
        
        assert response.quote_id is not None
        assert response.user_id == "u1"
        assert response.station_id == "st1"
        assert response.price_per_hour == 60
        assert response.deposit == 300
        s.commit()
        
        # Test quote validation
        quote_data = quote_service.get_and_validate_quote(response.quote_id)
        assert quote_data.id == response.quote_id
        assert quote_data.user_id == "u1"
        
        # Test quote consumption
        quote_service.consume_quote(response.quote_id)
        s.commit()
        
        # Verify quote is consumed
        quote = quote_repo.get_quote(response.quote_id)
        assert quote is None
