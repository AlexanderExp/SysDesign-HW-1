import uuid

import pytest


@pytest.mark.integration
def test_start_is_idempotent(
    api_client,
    test_user_id,
    test_station_id,
    cleanup_db,
):
    """
    Тест идемпотентности:

    - создаём quote
    - дважды вызываем /rentals/start с одним и тем же Idempotency-Key
    - ожидаем одинаковый order_id
    """
    # Создаём quote
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote_id = q_resp.json()["quote_id"]

    idem_key = str(uuid.uuid4())

    # Первый start
    s1 = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": idem_key},
    )
    assert s1.status_code == 200
    order_id_1 = s1.json()["order_id"]
    assert order_id_1

    # Повторный start с тем же ключом
    s2 = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote_id},
        headers={"Idempotency-Key": idem_key},
    )
    assert s2.status_code == 200
    order_id_2 = s2.json()["order_id"]
    assert order_id_2

    assert order_id_1 == order_id_2, (
        f"Идемпотентность нарушена: {order_id_1} != {order_id_2}"
    )


@pytest.mark.integration
def test_start_with_invalid_quote_returns_4xx(
    api_client,
    cleanup_db,
):
    """
    Тест ошибки при старте с невалидным quote:

    - вызываем /rentals/start с несуществующим quote_id
    - ожидаем 4xx (ошибка валидации/бизнес-логики, но не 2xx).
    """
    resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": "non-existing"},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    assert 400 <= resp.status_code < 500, (
        f"Ожидали 4xx на невалидный quote_id, "
        f"получили {resp.status_code} и тело {resp.text!r}"
    )
