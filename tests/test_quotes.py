import uuid

import pytest
from sqlalchemy import text


@pytest.mark.integration
def test_create_quote_persisted(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,  # noqa: ARG001
):
    resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )

    assert resp.status_code == 200
    body = resp.json()

    quote_id = body["quote_id"]
    assert quote_id

    # Проверяем, что запись появилась в таблице quotes
    row = db_session.execute(
        text("SELECT id, user_id, station_id FROM quotes WHERE id = :id"),
        {"id": quote_id},
    ).fetchone()

    assert row is not None, "Quote должен сохраниться в БД"
    assert row.id == quote_id
    assert row.user_id == test_user_id
    assert row.station_id == test_station_id


@pytest.mark.integration
def test_quote_expiration_cleanup(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,  # noqa: ARG001
):
    # Create quote
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    # Verify quote exists
    row = db_session.execute(
        text("SELECT id FROM quotes WHERE id = :id"),
        {"id": quote_id},
    ).fetchone()
    assert row is not None

    # Expire quote in DB
    db_session.execute(
        text(
            "UPDATE quotes SET expires_at = NOW() - INTERVAL '1 minute' WHERE id = :id"
        ),
        {"id": quote_id},
    )
    db_session.commit()

    # Try to use expired quote
    start_resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert 400 <= start_resp.status_code < 500
