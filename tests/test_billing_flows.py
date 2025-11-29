import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text


def _create_rental(api_client, test_user_id: str, test_station_id: str) -> str:
    """Создаёт quote + стартует аренду, возвращает order_id."""
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
    order_id = s_resp.json()["order_id"]
    return order_id


def _rewind_started_at(db_session, rental_id: str, minutes: int) -> None:
    """
    Сдвигаем started_at аренды назад на N минут, чтобы смоделировать "прошло время".
    """
    db_session.execute(
        text(
            f"UPDATE rentals "
            f"SET started_at = NOW() - INTERVAL '{minutes} minutes' "
            f"WHERE id = :id"
        ),
        {"id": rental_id},
    )
    db_session.commit()


def _get_payment_stats(db_session, rental_id: str):
    """
    Возвращает агрегаты по payment_attempts:

    - attempts_total: всего попыток
    - attempts_ok: успешных попыток
    - amount_sum: сумма успешных списаний
    """
    row = (
        db_session.execute(
            text(
                """
            SELECT
                COUNT(*)::int AS attempts_total,
                COALESCE(SUM(CASE WHEN success THEN 1 ELSE 0 END), 0)::int
                    AS attempts_ok,
                COALESCE(SUM(CASE WHEN success THEN amount ELSE 0 END), 0)::int
                    AS amount_sum
            FROM payment_attempts
            WHERE rental_id = :id
            """
            ),
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
    """Текущий долг по аренде."""
    row = db_session.execute(
        text("SELECT amount_total FROM debts WHERE rental_id = :id"),
        {"id": rental_id},
    ).fetchone()
    return int(row.amount_total) if row is not None else 0


def _get_rental_status(db_session, rental_id: str) -> str:
    """Текущий статус аренды из таблицы rentals."""
    row = db_session.execute(
        text("SELECT status FROM rentals WHERE id = :id"),
        {"id": rental_id},
    ).fetchone()
    return row.status if row is not None else ""


# ---------- Тесты ----------


@pytest.mark.integration
@pytest.mark.billing
@pytest.mark.slow
def test_periodic_billing_produces_successful_charges(
    api_client,
    db_session,
    test_user_id,
    test_station_id,
    wait_for_billing,
    cleanup_db,
):
    """
    Тест периодического биллинга:

    - создаём аренду
    - несколько раз "ускоряем время" через UPDATE started_at
    - ждём биллинг
    - ожидаем хотя бы одну успешную попытку списания и сумму > 0.
    """
    rental_id = _create_rental(api_client, test_user_id, test_station_id)

    tick = int(os.getenv("BILLING_TICK_SEC", "5"))
    wait_seconds = max(tick + 2, 5)

    # Несколько шагов "прошло времени"
    for step in range(3):
        # каждый раз отматываем начало аренды дальше в прошлое
        minutes = (step + 1) * 15
        _rewind_started_at(db_session, rental_id, minutes)
        wait_for_billing(wait_seconds)

    stats = _get_payment_stats(db_session, rental_id)
    debt = _get_debt_amount(db_session, rental_id)

    assert stats["attempts_ok"] >= 1, "Должна быть хотя бы одна успешная попытка"
    assert stats["amount_sum"] > 0, "Сумма успешных списаний должна быть > 0"
    # В этом тесте долг нам не критичен, но полезно зафиксировать, что он не отрицательный
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
    cleanup_db,
):
    """
    Тест выкупа с оплаченной арендой:

    - создаём аренду
    - сильно отматываем started_at в прошлое -> накапливается много платежей
    - ждём биллинг -> статус должен стать BUYOUT/FINISHED, долг = 0
    - ждём ещё несколько тиков -> новые попытки не должны появляться.
    """
    rental_id = _create_rental(api_client, test_user_id, test_station_id)

    tick = int(os.getenv("BILLING_TICK_SEC", "5"))
    wait_seconds = max(tick + 2, 5)

    # Сделаем вид, что аренда началась давно — например, 3 часа назад.
    _rewind_started_at(db_session, rental_id, minutes=180)
    wait_for_billing(wait_seconds * 2)

    stats_before = _get_payment_stats(db_session, rental_id)
    debt_before = _get_debt_amount(db_session, rental_id)
    status_before = _get_rental_status(db_session, rental_id)

    assert stats_before["amount_sum"] > 0, "К моменту buyout что-то должно быть списано"
    assert debt_before == 0, "Сценарий paid-only: долг должен быть 0"
    assert status_before in ("BUYOUT", "FINISHED"), (
        f"Ожидали BUYOUT/FINISHED, получили {status_before}"
    )

    # Дополнительное ожидание: после buyout не должно добавляться попыток/сумм
    wait_for_billing(wait_seconds * 2)

    stats_after = _get_payment_stats(db_session, rental_id)
    debt_after = _get_debt_amount(db_session, rental_id)
    status_after = _get_rental_status(db_session, rental_id)

    assert stats_after["attempts_total"] == stats_before["attempts_total"], (
        "После buyout не должно появляться новых попыток"
    )
    assert stats_after["amount_sum"] == stats_before["amount_sum"], (
        "После buyout сумма успешных списаний не должна меняться"
    )
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
    cleanup_db,
):
    """
    Тест выкупа с существующим долгом:

    - создаём аренду и даём ей немного "накопиться" (успешные списания)
    - затем вручную добавляем долг в таблицу debts
    - ждём биллинг, пока debt не уменьшится и статус не станет BUYOUT/FINISHED
    - потом ждём ещё немного и убеждаемся, что paid/debt больше не меняются.
    """
    rental_id = _create_rental(api_client, test_user_id, test_station_id)

    tick = int(os.getenv("BILLING_TICK_SEC", "5"))
    wait_seconds = max(tick + 2, 5)

    # Немного времени "прошло"
    _rewind_started_at(db_session, rental_id, minutes=60)
    wait_for_billing(wait_seconds * 2)

    # Снимем начальные показатели
    stats_initial = _get_payment_stats(db_session, rental_id)

    # Вручную добавляем долг (как будто несколько биллингов не смогли списать)
    initial_debt_amount = 150
    db_session.execute(
        text(
            """
            INSERT INTO debts (rental_id, amount_total, updated_at, attempts)
            VALUES (:id, :amount, NOW(), 0)
            ON CONFLICT (rental_id) DO UPDATE
              SET amount_total = debts.amount_total + EXCLUDED.amount_total,
                  updated_at = NOW()
            """
        ),
        {"id": rental_id, "amount": initial_debt_amount},
    )
    db_session.commit()

    debt_before = _get_debt_amount(db_session, rental_id)
    assert debt_before >= initial_debt_amount

    # Даём биллингу время попытаться забрать долг
    wait_for_billing(wait_seconds * 3)

    stats_after = _get_payment_stats(db_session, rental_id)
    debt_after = _get_debt_amount(db_session, rental_id)
    status_after = _get_rental_status(db_session, rental_id)

    # Долг должен уменьшиться или обнулиться
    assert debt_after <= debt_before, (
        f"Ожидали уменьшения долга, было {debt_before}, стало {debt_after}"
    )
    # Платежи могли увеличиться
    assert stats_after["amount_sum"] >= stats_initial["amount_sum"]
    # При достижении порога выкупа статус становится BUYOUT/FINISHED
    assert status_after in ("BUYOUT", "FINISHED")

    # Дополнительно убеждаемся, что после buyout paid/debt больше не трогаются
    wait_for_billing(wait_seconds * 2)

    stats_final = _get_payment_stats(db_session, rental_id)
    debt_final = _get_debt_amount(db_session, rental_id)
    status_final = _get_rental_status(db_session, rental_id)

    assert stats_final["attempts_total"] == stats_after["attempts_total"], (
        "После buyout не должно появляться новых попыток списания"
    )
    assert stats_final["amount_sum"] == stats_after["amount_sum"], (
        "После buyout сумма успешных списаний не должна меняться"
    )
    assert debt_final == debt_after, "После buyout долг не должен меняться"
    assert status_final in ("BUYOUT", "FINISHED")
