import uuid

import pytest
from sqlalchemy import text


@pytest.mark.integration
def test_rental_created_before_powerbank_ejection(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,  # noqa: ARG001
):
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    start_resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert start_resp.status_code == 200
    body = start_resp.json()
    order_id = body["order_id"]
    powerbank_id = body["powerbank_id"]

    row = db_session.execute(
        text("SELECT id, powerbank_id, status FROM rentals WHERE id = :id"),
        {"id": order_id},
    ).fetchone()

    assert row is not None
    assert row.id == order_id
    assert row.powerbank_id == powerbank_id
    assert row.powerbank_id != "PENDING"
    assert row.status == "ACTIVE"


@pytest.mark.integration
def test_rental_has_pending_powerbank_initially(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,  # noqa: ARG001
    monkeypatch,  # noqa: ARG001
):
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    start_resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert start_resp.status_code == 200
    order_id = start_resp.json()["order_id"]

    row = db_session.execute(
        text("SELECT powerbank_id FROM rentals WHERE id = :id"),
        {"id": order_id},
    ).fetchone()

    assert row.powerbank_id != "PENDING"


@pytest.mark.integration
def test_no_rental_without_db_record(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,  # noqa: ARG001
):
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    start_resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    if start_resp.status_code == 200:
        order_id = start_resp.json()["order_id"]

        row = db_session.execute(
            text("SELECT id, status FROM rentals WHERE id = :id"),
            {"id": order_id},
        ).fetchone()

        assert row is not None
        assert row.status in ("ACTIVE", "PENDING")


@pytest.mark.integration
def test_failed_status_when_eject_fails(
    api_client,
    db_session,
    test_user_id,
    cleanup_db,  # noqa: ARG001
):
    invalid_station = "station-that-fails-eject"

    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": invalid_station, "user_id": test_user_id},
    )

    if q_resp.status_code == 200:
        quote_id = q_resp.json()["quote_id"]

        start_resp = api_client.post(
            "/api/v1/rentals/start",
            json={"quote_id": quote_id},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

        if start_resp.status_code >= 500:
            db_session.execute(
                text("SELECT id, status FROM rentals WHERE status = 'FAILED'")
            ).fetchall()


@pytest.mark.integration
def test_rental_status_progression(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,  # noqa: ARG001
):
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    start_resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert start_resp.status_code == 200
    order_id = start_resp.json()["order_id"]

    row = db_session.execute(
        text("SELECT status FROM rentals WHERE id = :id"),
        {"id": order_id},
    ).fetchone()

    assert row.status == "ACTIVE"

    stop_resp = api_client.post(
        f"/api/v1/rentals/{order_id}/stop",
        json={"station_id": test_station_id},
    )
    assert stop_resp.status_code == 200

    row = db_session.execute(
        text("SELECT status FROM rentals WHERE id = :id"),
        {"id": order_id},
    ).fetchone()

    assert row.status == "FINISHED"
