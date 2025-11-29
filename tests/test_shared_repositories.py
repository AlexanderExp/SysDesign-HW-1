import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from shared.db.models import (
    Base,
    Rental,
    Debt,
    Quote,
    IdempotencyKey,
    PaymentAttempt,
)
from shared.db.repositories.idempotency import IdempotencyRepository
from shared.db.repositories.payment import PaymentRepository
from shared.db.repositories.quote import QuoteRepository
from shared.db.repositories.rental import RentalRepository
from shared.db.repositories.debt import DebtRepository


# ---------- IdempotencyRepository ----------


def test_idempotency_repository_empty(db_session):
    repo = IdempotencyRepository(db_session)

    assert repo.get_idempotency_key("no-such-key") is None
    assert repo.get_cached_response("no-such-key") is None


def test_idempotency_repository_create_and_get_cached_response(db_session):
    repo = IdempotencyRepository(db_session)

    key = "idem-1"
    scope = "rentals:start"
    user_id = "user-1"
    response = {"order_id": "o-123", "status": "ok"}

    repo.create_idempotency_key(key, scope, user_id, response)

    record = repo.get_idempotency_key(key)
    assert record is not None
    assert record.key == key
    assert record.scope == scope
    assert record.user_id == user_id
    assert json.loads(record.response_json) == response

    cached = repo.get_cached_response(key)
    assert cached == response


# ---------- PaymentRepository ----------


def test_payment_repository_create_and_total_paid(db_session):
    repo = PaymentRepository(db_session)

    rental_id = "r1"
    # 2 успешных + 1 неуспешная
    repo.create_payment_attempt(rental_id, 100, True)
    repo.create_payment_attempt(rental_id, 200, True)
    repo.create_payment_attempt(rental_id, 300, False, error="fail")

    total = repo.get_total_paid(rental_id)
    assert total == 300  # 100 + 200

    attempts = repo.get_payment_attempts(rental_id)
    assert len(attempts) == 3

    successful = repo.get_successful_payments(rental_id)
    assert len(successful) == 2
    assert all(a.success for a in successful)


def test_payment_repository_total_paid_zero_for_unknown_rental(db_session):
    repo = PaymentRepository(db_session)
    assert repo.get_total_paid("unknown") == 0


# ---------- QuoteRepository ----------


def test_quote_repository_create_get_delete(db_session):
    repo = QuoteRepository(db_session)

    quote_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=1)

    repo.create_quote(
        quote_id=quote_id,
        user_id="user-42",
        station_id="station-1",
        price_per_hour=150,
        free_period_min=10,
        deposit=500,
        expires_at=expires_at,
        created_at=now,
    )

    q = repo.get_quote(quote_id)
    assert q is not None
    assert q.id == quote_id
    assert q.user_id == "user-42"
    assert q.station_id == "station-1"
    assert q.price_per_hour == 150
    assert q.free_period_min == 10
    assert q.deposit == 500
    assert q.expires_at == expires_at

    repo.delete_quote(quote_id)
    assert repo.get_quote(quote_id) is None

    # повторный delete не падает
    repo.delete_quote(quote_id)


# ---------- RentalRepository ----------


def _make_rental(
    rental_id: str,
    user_id: str = "user-1",
    status: str = "ACTIVE",
    started_at: datetime | None = None,
) -> Rental:
    if started_at is None:
        started_at = datetime.now(timezone.utc)

    return Rental(
        id=rental_id,
        user_id=user_id,
        powerbank_id="pb-1",
        price_per_hour=120,
        free_period_min=10,
        deposit=500,
        status=status,
        total_amount=0,
        started_at=started_at,
        finished_at=None,
    )


def test_rental_repository_get_active_ids_and_update_amount(db_session):
    repo = RentalRepository(db_session)

    r1 = _make_rental("r1", status="ACTIVE")
    r2 = _make_rental("r2", status="FINISHED")
    db_session.add_all([r1, r2])
    db_session.commit()

    active_ids = repo.get_active_rental_ids()
    assert "r1" in active_ids
    assert "r2" not in active_ids

    # update_total_amount на существующей аренде
    updated = repo.update_total_amount("r1", 300)
    assert updated is True
    assert repo.get_by_id("r1").total_amount == 300

    # update_total_amount на несуществующей
    updated = repo.update_total_amount("no-such", 100)
    assert updated is False


def test_rental_repository_finish_and_buyout(db_session):
    repo = RentalRepository(db_session)

    r = _make_rental("r3", status="ACTIVE")
    db_session.add(r)
    db_session.commit()

    # finish_rental
    finished = repo.finish_rental("r3", status="FINISHED")
    assert finished is True
    db_r = repo.get_by_id("r3")
    assert db_r.status == "FINISHED"
    assert db_r.finished_at is not None

    # повторный вызов для уже не ACTIVE аренды не должен ничего менять
    finished_again = repo.finish_rental("r3", status="BUYOUT")
    assert finished_again is False
    assert repo.get_by_id("r3").status == "FINISHED"

    # set_buyout_status для ACTIVE
    r2 = _make_rental("r4", status="ACTIVE")
    db_session.add(r2)
    db_session.commit()

    buyout = repo.set_buyout_status("r4")
    assert buyout is True
    assert repo.get_by_id("r4").status == "BUYOUT"


def test_rental_repository_calculate_due_amount_with_free_period(db_session):
    repo = RentalRepository(db_session)

    start = datetime.now(timezone.utc)
    rental = _make_rental("r5", started_at=start)
    rental.price_per_hour = 360  # 1 минута = 6 единиц
    rental.free_period_min = 5
    db_session.add(rental)
    db_session.commit()

    # до конца free-периода
    t_free = start + timedelta(minutes=5)
    due = repo.calculate_due_amount(rental, t_free)
    assert due == 0

    # через 10 минут после старта (5 платных минут)
    t_after = start + timedelta(minutes=10)
    due = repo.calculate_due_amount(rental, t_after)
    # billable_seconds = 5 * 60, (360 * 300) // 3600 = 30
    assert due == 30

    # если started_at None — 0
    rental_no_start = _make_rental("r6", status="ACTIVE")
    rental_no_start.started_at = None
    assert repo.calculate_due_amount(rental_no_start, t_after) == 0


# ---------- DebtRepository ----------


def test_debt_repository_add_and_get_amount(db_session):
    repo = DebtRepository(db_session)
    rental_id = "r-debt-1"

    assert repo.get_amount(rental_id) == 0

    repo.add_debt(rental_id, 200)
    assert repo.get_amount(rental_id) == 200

    # повторное добавление
    repo.add_debt(rental_id, 50)
    assert repo.get_amount(rental_id) == 250


def test_debt_repository_reduce_and_attempts(db_session):
    repo = DebtRepository(db_session)
    rental_id = "r-debt-2"

    # создаём долг 300
    repo.add_debt(rental_id, 300)
    debt = repo.get_by_rental_id(rental_id)
    assert debt is not None
    assert debt.amount_total == 300

    # попытка списать больше, чем есть — False
    assert repo.reduce_debt(rental_id, 400) is False
    assert repo.get_amount(rental_id) == 300

    # успешное уменьшение
    assert repo.reduce_debt(rental_id, 200) is True
    debt = repo.get_by_rental_id(rental_id)
    assert debt.amount_total == 100
    # attempts должен сброситься в 0
    assert debt.attempts == 0

    # increment_attempts
    repo.increment_attempts(rental_id)
    repo.increment_attempts(rental_id)
    debt = repo.get_by_rental_id(rental_id)
    assert debt.attempts == 2
    assert debt.last_attempt_at is not None


def test_debt_repository_should_retry_debt(db_session):
    repo = DebtRepository(db_session)
    rental_id = "r-debt-3"

    # без долга — нельзя ретраить
    assert repo.should_retry_debt(rental_id, backoff_seconds=10) is False

    # создаём долг и ни разу не пытались — можно ретраить сразу
    repo.add_debt(rental_id, 100)
    assert repo.should_retry_debt(rental_id, backoff_seconds=10) is True

    # выставим last_attempt_at = сейчас
    debt = repo.get_by_rental_id(rental_id)
    debt.last_attempt_at = datetime.now(timezone.utc)
    db_session.commit()

    assert repo.should_retry_debt(rental_id, backoff_seconds=3600) is False


def test_debt_repository_attach_debt(db_session):
    repo = DebtRepository(db_session)
    rental_id = "r-debt-4"
    now = datetime.now(timezone.utc)

    # новый долг
    repo.attach_debt(rental_id, 50, now)
    debt = repo.get_by_rental_id(rental_id)
    assert debt is not None
    assert debt.amount_total == 50
    assert debt.updated_at == now

    # плюс ещё 70
    later = now + timedelta(minutes=5)
    repo.attach_debt(rental_id, 70, later)
    debt = repo.get_by_rental_id(rental_id)
    assert debt.amount_total == 120
    assert debt.updated_at == later
