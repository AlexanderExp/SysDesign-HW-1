import uuid

import pytest
from sqlalchemy import text


@pytest.mark.integration
def test_rental_stop_flow(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,  # noqa: ARG001
):
    """Test complete rental flow: create -> start -> stop."""
    # Create quote
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    # Start rental
    s_resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert s_resp.status_code == 200
    order_id = s_resp.json()["order_id"]

    # Verify rental is active
    row = db_session.execute(
        text("SELECT status FROM rentals WHERE id = :id"),
        {"id": order_id},
    ).fetchone()
    assert row.status == "ACTIVE"

    # Stop rental
    stop_resp = api_client.post(
        f"/api/v1/rentals/{order_id}/stop",
        json={"station_id": test_station_id},
    )
    assert stop_resp.status_code == 200

    # Verify rental is finished
    row = db_session.execute(
        text("SELECT status FROM rentals WHERE id = :id"),
        {"id": order_id},
    ).fetchone()
    assert row.status == "FINISHED"
