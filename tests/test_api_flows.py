import uuid

import pytest
from sqlalchemy import text


@pytest.mark.integration
def test_health_ok(api_client):
    data = api_client.get("/api/v1/health")
    assert isinstance(data, dict)
    assert data  # не пустой словарь


@pytest.mark.integration
def test_start_is_idempotent(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,  # noqa: ARG001
):
    # 1. создаём quote
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    idem_key = str(uuid.uuid4())

    # 2. первый start
    s1 = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": idem_key},
    )
    assert s1.status_code == 200
    body1 = s1.json()
    order_id_1 = body1["order_id"]

    # 3. повторный start с тем же ключом
    s2 = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": idem_key},
    )
    assert s2.status_code == 200
    body2 = s2.json()
    order_id_2 = body2["order_id"]

    assert order_id_1 == order_id_2

    # В БД должна быть ровно одна аренда с таким id
    row = db_session.execute(
        text("SELECT COUNT(*) AS cnt FROM rentals WHERE id = :id"),
        {"id": order_id_1},
    ).fetchone()
    assert row.cnt == 1


@pytest.mark.integration
def test_start_with_invalid_quote_returns_4xx(
    api_client,
    cleanup_db,  # noqa: ARG001
):
    resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": "non-existing-quote-id"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    assert 400 <= resp.status_code < 500, (
        f"Ожидали 4xx, получили {resp.status_code}, тело: {resp.text!r}"
    )


@pytest.mark.integration
def test_start_with_expired_quote_returns_4xx(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,  # noqa: ARG001
):
    # 1. создаём quote
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    # 2. протухаем его в БД
    db_session.execute(
        text(
            "UPDATE quotes SET expires_at = NOW() - INTERVAL '5 minutes' WHERE id = :id"
        ),
        {"id": quote_id},
    )
    db_session.commit()

    # 3. пробуем стартануть аренду
    start_resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    assert 400 <= start_resp.status_code < 500, (
        f"Ожидали 4xx при старте с протухшим quote, "
        f"получили {start_resp.status_code}, тело: {start_resp.text!r}"
    )
