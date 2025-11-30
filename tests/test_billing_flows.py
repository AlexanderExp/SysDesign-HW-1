import os
import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import text

# ---------- Вспомогательные штуки ----------


@dataclass
class BillingConfig:
    tick_sec: int
    r_buyout: int


def _get_billing_config() -> BillingConfig:
    tick_sec = int(os.getenv("BILLING_TICK_SEC", "5"))
    r_buyout = int(os.getenv("R_BUYOUT", "50"))

    # защитимся от совсем странных значений
    tick_sec = max(tick_sec, 1)
    r_buyout = max(r_buyout, 1)

    return BillingConfig(tick_sec=tick_sec, r_buyout=r_buyout)


def _create_rental_with_quote(api_client, test_user_id: str, test_station_id: str):
    q_resp = api_client.post(
        "/api/v1/rentals/quote",
        json={"station_id": test_station_id, "user_id": test_user_id},
    )
    assert q_resp.status_code == 200
    quote = q_resp.json()

    s_resp = api_client.post(
        "/api/v1/rentals/start",
        json={"quote_id": quote["quote_id"]},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert s_resp.status_code == 200
    order_id = s_resp.json()["order_id"]
    return order_id, quote


def _rewind_started_at(db_session, rental_id: str, minutes: int) -> None:
    db_session.execute(
        text(
            f"UPDATE rentals "
            f"SET started_at = NOW() - INTERVAL '{minutes} minutes' "
            f"WHERE id = :id"
        ),
        {"id": rental_id},
    )
    db_session.commit()


def _get_payment_stats(billing_db_session, rental_id: str):
    row = (
        billing_db_session.execute(
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


def _get_debt_amount(billing_db_session, rental_id: str) -> int:
    row = billing_db_session.execute(
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


def _minutes_needed_for_buyout(quote: dict, cfg: BillingConfig) -> int:
    """
    Прикидываем, сколько минут нужно, чтобы по тарифу гарантированно
    набежать до buyout-порога R_BUYOUT.

    Формула грубая, с запасом:
    - учитываем бесплатный период free_period_min;
    - считаем, что дальше начисление идёт линейно: price_per_hour * часы;
    - умножаем на safety_factor, чтобы точно перекрыть порог.
    """
    price_per_hour = max(int(quote["price_per_hour"]), 1)
    free_min = int(quote["free_period_min"])

    safety_factor = 1.5  # небольшой запас, чтобы точно пересечь порог
    hours_needed = (cfg.r_buyout * safety_factor) / price_per_hour
    minutes_needed = int(hours_needed * 60)

    total_minutes = free_min + minutes_needed

    # не даём совсем маленькое значение
    return max(total_minutes, free_min + 10)


def _wait_until_status_in(
    db_session,
    rental_id: str,
    wait_for_billing,
    cfg: BillingConfig,
    expected_statuses,
    max_rounds: int = 10,
):
    """
    Ждём, пока статус аренды станет одним из expected_statuses, с ограничением по количеству раундов.
    Между раундами ждём несколько тиков биллинга.
    """
    wait_seconds = max(cfg.tick_sec * 2, 5)

    status = _get_rental_status(db_session, rental_id)
    rounds = 0

    while status not in expected_statuses and rounds < max_rounds:
        wait_for_billing(wait_seconds)
        status = _get_rental_status(db_session, rental_id)
        rounds += 1

    return status


# ---------- Тесты ----------


@pytest.mark.integration
@pytest.mark.billing
@pytest.mark.slow
def test_periodic_billing_produces_successful_charges(
    api_client,
    db_session,
    billing_db_session,
    test_user_id,
    test_station_id,
    wait_for_billing,
    cleanup_db,  # noqa: ARG001
):
    """
    Тест периодического биллинга:

    - создаём аренду
    - несколько раз "ускоряем время" через UPDATE started_at
    - ждём биллинг
    - ожидаем хотя бы одну успешную попытку списания и сумму > 0.

    Адаптация к конфигу:
    - читаем BILLING_TICK_SEC и ждём в районе нескольких тиков;
    - количество шагов и интервал времени не зашиты жёстко.
    """
    cfg = _get_billing_config()
    rental_id, _ = _create_rental_with_quote(api_client, test_user_id, test_station_id)

    wait_seconds = max(cfg.tick_sec * 2, 5)

    for step in range(3):
        minutes = (step + 1) * 15
        _rewind_started_at(db_session, rental_id, minutes)
        wait_for_billing(wait_seconds)

    stats = _get_payment_stats(billing_db_session, rental_id)
    debt = _get_debt_amount(billing_db_session, rental_id)

    assert stats["attempts_ok"] >= 1, "Должна быть хотя бы одна успешная попытка"
    assert stats["amount_sum"] > 0, "Сумма успешных списаний должна быть > 0"
    assert debt >= 0


@pytest.mark.integration
@pytest.mark.billing
@pytest.mark.slow
def test_buyout_paid_only_stops_new_charges(
    api_client,
    db_session,
    billing_db_session,
    test_user_id,
    test_station_id,
    wait_for_billing,
    cleanup_db,  # noqa: ARG001
):
    """
    Тест выкупа с оплаченной арендой (без долга):

    - создаём аренду
    - отматываем started_at так далеко назад, чтобы по текущему тарифу и R_BUYOUT
      гарантированно можно было достигнуть порога выкупа
    - ждём, пока статус станет BUYOUT/FINISHED
    - фиксируем число попыток и сумму
    - ждём ещё несколько тиков — ничего не должно измениться.

    Адаптация к конфигу:
    - R_BUYOUT берём из env;
    - длину "отмотки" считаем из price_per_hour и free_period_min оффера;
    - ожидание делаем через цикл с несколькими раундами.
    """
    cfg = _get_billing_config()
    rental_id, quote = _create_rental_with_quote(
        api_client, test_user_id, test_station_id
    )

    # Считаем, сколько минут нужно, чтобы точно пересечь порог выкупа
    minutes_for_buyout = _minutes_needed_for_buyout(quote, cfg)
    _rewind_started_at(db_session, rental_id, minutes_for_buyout)

    # Ждём, пока аренда попадёт в BUYOUT/FINISHED
    status_before = _wait_until_status_in(
        db_session,
        rental_id,
        wait_for_billing,
        cfg,
        expected_statuses=("BUYOUT", "FINISHED"),
        max_rounds=10,
    )

    stats_before = _get_payment_stats(billing_db_session, rental_id)
    debt_before = _get_debt_amount(billing_db_session, rental_id)

    assert stats_before["amount_sum"] > 0
    assert debt_before == 0
    assert status_before in ("BUYOUT", "FINISHED")

    # Дополнительное ожидание: после buyout не должно появляться попыток/сумм
    status_after = _wait_until_status_in(
        db_session,
        rental_id,
        wait_for_billing,
        cfg,
        expected_statuses=("BUYOUT", "FINISHED"),
        max_rounds=3,
    )

    stats_after = _get_payment_stats(billing_db_session, rental_id)
    debt_after = _get_debt_amount(billing_db_session, rental_id)

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
    billing_db_session,
    test_user_id,
    test_station_id,
    wait_for_billing,
    cleanup_db,  # noqa: ARG001
):
    """
    Тест выкупа с существующим долгом:

    - создаём аренду, даём ей немного накопить успешных платежей
    - вручную добавляем долг (не меньше R_BUYOUT, чтобы сценарий был достижим)
    - ждём, пока биллинг попробует собрать долг и доведёт аренду до BUYOUT/FINISHED
    - потом ждём ещё немного и проверяем, что paid/debt/attempts дальше не меняются.

    Адаптация к конфигу:
    - величину долга берём как max(R_BUYOUT, некий минимум);
    - ожидание статуса — через цикл с несколькими раундами.
    """
    cfg = _get_billing_config()
    rental_id, quote = _create_rental_with_quote(
        api_client, test_user_id, test_station_id
    )

    wait_seconds = max(cfg.tick_sec * 2, 5)

    # Немного времени "прошло", чтобы появились первые платежи
    # Берём время меньше, чем нужно для buyout, чтобы был нормальный "хвост" до порога
    _rewind_started_at(db_session, rental_id, minutes=quote["free_period_min"] + 30)
    wait_for_billing(wait_seconds * 2)

    stats_initial = _get_payment_stats(billing_db_session, rental_id)

    # Вручную добавляем долг: не меньше R_BUYOUT, чтобы buyout точно был достижим
    initial_debt_amount = max(cfg.r_buyout, 100)
    billing_db_session.execute(
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
    billing_db_session.commit()

    debt_before = _get_debt_amount(billing_db_session, rental_id)
    assert debt_before >= initial_debt_amount

    # Даём биллингу время попытаться забрать долг и довести аренду до buyout
    status_after = _wait_until_status_in(
        db_session,
        rental_id,
        wait_for_billing,
        cfg,
        expected_statuses=("BUYOUT", "FINISHED"),
        max_rounds=10,
    )

    stats_after = _get_payment_stats(billing_db_session, rental_id)
    debt_after = _get_debt_amount(billing_db_session, rental_id)

    assert debt_after <= debt_before
    assert stats_after["amount_sum"] >= stats_initial["amount_sum"]
    assert status_after in ("BUYOUT", "FINISHED")

    # Дополнительно убеждаемся, что после buyout paid/debt/attempts не меняются
    status_final = _wait_until_status_in(
        db_session,
        rental_id,
        wait_for_billing,
        cfg,
        expected_statuses=("BUYOUT", "FINISHED"),
        max_rounds=3,
    )

    stats_final = _get_payment_stats(billing_db_session, rental_id)
    debt_final = _get_debt_amount(billing_db_session, rental_id)

    assert stats_final["attempts_total"] == stats_after["attempts_total"]
    assert stats_final["amount_sum"] == stats_after["amount_sum"]
    assert debt_final == debt_after
    assert status_final in ("BUYOUT", "FINISHED")
