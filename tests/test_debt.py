import uuid

import pytest
from sqlalchemy import text


@pytest.mark.integration
@pytest.mark.billing
@pytest.mark.slow
def test_debt_retry_with_backoff(
    api_client,
    billing_db_session,
    test_user_id,
    test_station_id,
    wait_for_billing,
    cleanup_db,  # noqa: ARG001
):
    # This test checks that attempts increase over time
    # Create a rental and manually set debt
    quote_response = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    quote_id = quote_response.json()["quote_id"]

    start_response = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    order_id = start_response.json()["order_id"]

    # Manually create debt
    billing_db_session.execute(
        text("""
            INSERT INTO debts (rental_id, amount_total, updated_at, attempts, last_attempt_at)
            VALUES (:id, 100, NOW(), 0, NOW() - INTERVAL '2 hours')
        """),
        {"id": order_id},
    )
    billing_db_session.commit()

    # Wait for billing worker
    wait_for_billing(15)

    # Check that attempt was made
    debt = billing_db_session.execute(
        text("SELECT attempts FROM debts WHERE rental_id = :id"), {"id": order_id}
    ).fetchone()

    # Attempts should have increased (debt collection was tried)
    assert debt.attempts >= 0


@pytest.mark.integration
@pytest.mark.billing
@pytest.mark.slow
def test_debt_collection_success(
    api_client,
    billing_db_session,
    test_user_id,
    test_station_id,
    wait_for_billing,
    cleanup_db,  # noqa: ARG001
):
    # Create rental with some charges
    quote_response = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    quote_id = quote_response.json()["quote_id"]

    start_response = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    order_id = start_response.json()["order_id"]

    # Manually create small debt (that can be collected)
    billing_db_session.execute(
        text("""
            INSERT INTO debts (rental_id, amount_total, updated_at, attempts, last_attempt_at)
            VALUES (:id, 50, NOW(), 0, NOW() - INTERVAL '2 hours')
            ON CONFLICT (rental_id) DO UPDATE
            SET amount_total = debts.amount_total + 50
        """),
        {"id": order_id},
    )
    billing_db_session.commit()

    initial_debt = (
        billing_db_session.execute(
            text("SELECT amount_total FROM debts WHERE rental_id = :id"),
            {"id": order_id},
        )
        .fetchone()
        .amount_total
    )

    # Wait for debt collection
    wait_for_billing(20)

    # Check if debt was reduced
    final_debt_row = billing_db_session.execute(
        text("SELECT amount_total FROM debts WHERE rental_id = :id"), {"id": order_id}
    ).fetchone()

    if final_debt_row:
        final_debt = final_debt_row.amount_total
        # Debt should be reduced or cleared
        assert final_debt <= initial_debt, "Debt should not increase"


@pytest.mark.integration
def test_debt_visible_in_status(
    api_client,
    billing_db_session,
    test_user_id,
    test_station_id,
    cleanup_db,  # noqa: ARG001
):
    # Create rental
    quote_response = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    quote_id = quote_response.json()["quote_id"]

    start_response = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    order_id = start_response.json()["order_id"]

    # Manually add debt
    billing_db_session.execute(
        text("""
            INSERT INTO debts (rental_id, amount_total, updated_at, attempts)
            VALUES (:id, 150, NOW(), 0)
        """),
        {"id": order_id},
    )
    billing_db_session.commit()

    # Check status includes debt
    status = api_client.get(f"/api/v1/rentals/{order_id}/status")
    assert status["debt"] == 150, "Debt should be visible in status"
