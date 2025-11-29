import uuid

import pytest
from sqlalchemy import text


@pytest.mark.integration
def test_create_quote_persisted(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,
):
    """Оффер создаётся через API и сохраняется в БД."""
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
def test_start_with_expired_quote_returns_4xx(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    cleanup_db,
):
    """
    Тест протухшего оффера:

    1. Создаём свежий quote через API
    2. Насильно протухаем его в БД (expires_at < now)
    3. Пытаемся стартовать аренду — ждём 4xx.
    """
    # 1. Создаём оффер
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    # 2. Протухаем его в БД
    db_session.execute(
        text(
            "UPDATE quotes SET expires_at = NOW() - INTERVAL '5 minutes' WHERE id = :id"
        ),
        {"id": quote_id},
    )
    db_session.commit()

    # 3. Пытаемся стартануть аренду с протухшим quote
    start_resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    assert 400 <= start_resp.status_code < 500, (
        f"Ожидали 4xx при старте с протухшим quote, "
        f"получили {start_resp.status_code} и тело {start_resp.text!r}"
    )
