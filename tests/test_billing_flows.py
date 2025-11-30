import os
import uuid

import pytest
from sqlalchemy import text


def _create_rental(api_client, test_user_id: str, test_station_id: str) -> str:
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    s_resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert s_resp.status_code == 200
    return s_resp.json()["order_id"]


def _rewind_started_at(db_session, rental_id: str, minutes: int) -> None:
    db_session.execute(
        text(
            f"UPDATE rentals SET started_at = NOW() - INTERVAL '{minutes} minutes' WHERE id = :id"
        ),
        {"id": rental_id},
    )
    db_session.commit()


def _get_payment_stats(db_session, rental_id: str):
    row = (
        db_session.execute(
            text("""
            SELECT
                COUNT(*)::int AS attempts_total,
                COALESCE(SUM(CASE WHEN success THEN 1 ELSE 0 END), 0)::int AS attempts_ok,
                COALESCE(SUM(CASE WHEN success THEN amount ELSE 0 END), 0)::int AS amount_sum
            FROM payment_attempts
            WHERE rental_id = :id
            """),
            {"id": rental_id},
        )
        .mappings()
        .one()
    )
    return {
        "attempts_total": row["attempts_total"],
        "attempts_ok": row["attempts_ok"],
        "amount_sum": row["amount_sum"],
    }


def _get_debt_amount(db_session, rental_id: str) -> int:
    row = db_session.execute(
        text("SELECT amount_total FROM debts WHERE rental_id = :id"),
        {"id": rental_id},
    ).fetchone()
    return int(row.amount_total) if row is not None else 0


def _get_rental_status(db_session, rental_id: str) -> str:
    row = db_session.execute(
        text("SELECT status FROM rentals WHERE id = :id"),
        {"id": rental_id},
    ).fetchone()
    return row.status if row is not None else ""


@pytest.mark.integration
@pytest.mark.billing
@pytest.mark.slow
def test_periodic_billing_produces_successful_charges(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    wait_for_billing,
    cleanup_db,  # noqa: ARG001
):
    rental_id = _create_rental(api_client, test_user_id, test_station_id)
    tick = int(os.getenv("BILLING_TICK_SEC", "5"))
    wait_seconds = max(tick + 2, 5)

    for step in range(3):
        minutes = (step + 1) * 15
        _rewind_started_at(db_session, rental_id, minutes)
        wait_for_billing(wait_seconds)

    stats = _get_payment_stats(db_session, rental_id)
    debt = _get_debt_amount(db_session, rental_id)

    assert stats["attempts_ok"] >= 1
    assert stats["amount_sum"] > 0
    assert debt >= 0


@pytest.mark.integration
@pytest.mark.billing
@pytest.mark.slow
def test_buyout_paid_only_stops_new_charges(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    wait_for_billing,
    cleanup_db,  # noqa: ARG001
):
    rental_id = _create_rental(api_client, test_user_id, test_station_id)
    tick = int(os.getenv("BILLING_TICK_SEC", "5"))
    wait_seconds = max(tick + 2, 5)

    _rewind_started_at(db_session, rental_id, minutes=180)
    wait_for_billing(wait_seconds * 2)

    stats_before = _get_payment_stats(db_session, rental_id)
    debt_before = _get_debt_amount(db_session, rental_id)
    status_before = _get_rental_status(db_session, rental_id)

    assert stats_before["amount_sum"] > 0
    assert debt_before == 0
    assert status_before in ("BUYOUT", "FINISHED")

    wait_for_billing(wait_seconds * 2)

    stats_after = _get_payment_stats(db_session, rental_id)
    debt_after = _get_debt_amount(db_session, rental_id)
    status_after = _get_rental_status(db_session, rental_id)

    assert stats_after["attempts_total"] == stats_before["attempts_total"]
    assert stats_after["amount_sum"] == stats_before["amount_sum"]
    assert debt_after == debt_before == 0
    assert status_after in ("BUYOUT", "FINISHED")


@pytest.mark.integration
@pytest.mark.billing
@pytest.mark.slow
def test_buyout_with_existing_debt_collected_and_stops(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    wait_for_billing,
    cleanup_db,  # noqa: ARG001
):
    rental_id = _create_rental(api_client, test_user_id, test_station_id)
    tick = int(os.getenv("BILLING_TICK_SEC", "5"))
    wait_seconds = max(tick + 2, 5)

    _rewind_started_at(db_session, rental_id, minutes=60)
    wait_for_billing(wait_seconds * 2)

    stats_initial = _get_payment_stats(db_session, rental_id)

    initial_debt_amount = 150
    db_session.execute(
        text("""
            INSERT INTO debts (rental_id, amount_total, updated_at, attempts)
            VALUES (:id, :amount, NOW(), 0)
            ON CONFLICT (rental_id) DO UPDATE
              SET amount_total = debts.amount_total + EXCLUDED.amount_total,
                  updated_at = NOW()
            """),
        {"id": rental_id, "amount": initial_debt_amount},
    )
    db_session.commit()

    debt_before = _get_debt_amount(db_session, rental_id)
    assert debt_before >= initial_debt_amount

    wait_for_billing(wait_seconds * 3)

    stats_after = _get_payment_stats(db_session, rental_id)
    debt_after = _get_debt_amount(db_session, rental_id)
    status_after = _get_rental_status(db_session, rental_id)

    assert debt_after <= debt_before
    assert stats_after["amount_sum"] >= stats_initial["amount_sum"]
    assert status_after in ("BUYOUT", "FINISHED")

    wait_for_billing(wait_seconds * 2)

    stats_final = _get_payment_stats(db_session, rental_id)
    debt_final = _get_debt_amount(db_session, rental_id)
    status_final = _get_rental_status(db_session, rental_id)

    assert stats_final["attempts_total"] == stats_after["attempts_total"]
    assert stats_final["amount_sum"] == stats_after["amount_sum"]
    assert debt_final == debt_after
    assert status_final in ("BUYOUT", "FINISHED")
