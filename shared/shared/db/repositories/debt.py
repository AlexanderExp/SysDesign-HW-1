from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.db.models import Debt


class DebtRepository:
    def __init__(self, session: Session):
        self.session = session

    # --- Базовые операции ---

    def get_by_rental_id(self, rental_id: str) -> Optional[Debt]:
        return self.session.get(Debt, rental_id)

    def get_amount(self, rental_id: str) -> int:
        debt = self.get_by_rental_id(rental_id)
        return int(debt.amount_total) if debt else 0

    # --- Добавление / изменение долга ---

    def add_debt(self, rental_id: str, amount: int) -> None:
        """
        Увеличивает долг по аренде (или создаёт его, если записи ещё нет).
        """
        now = datetime.now(timezone.utc)
        debt = self.get_by_rental_id(rental_id)

        if debt:
            debt.amount_total += amount
            debt.updated_at = now
            logger.debug(
                "Updated debt for rental {}: +{} (total: {})",
                rental_id,
                amount,
                debt.amount_total,
            )
        else:
            debt = Debt(
                rental_id=rental_id,
                amount_total=amount,
                updated_at=now,
                attempts=0,
                last_attempt_at=None,
            )
            self.session.add(debt)
            logger.debug(
                "Created new debt for rental {}: amount={}",
                rental_id,
                amount,
            )

    def reduce_debt(self, rental_id: str, amount: int) -> bool:
        """
        Уменьшает долг на amount.

        Возвращает True, если получилось уменьшить (и долг был >= amount),
        иначе False (в этом случае ничего не меняем).
        """
        debt = self.get_by_rental_id(rental_id)
        current = debt.amount_total if debt else 0

        if not debt or current < amount:
            logger.debug(
                "Cannot reduce debt for rental {} by {} (current: {})",
                rental_id,
                amount,
                current,
            )
            return False

        debt.amount_total = current - amount
        debt.updated_at = datetime.now(timezone.utc)
        # успешное погашение — попытки обнуляем
        debt.attempts = 0
        debt.last_attempt_at = None

        logger.debug(
            "Reduced debt for rental {}: -{} (remaining: {})",
            rental_id,
            amount,
            debt.amount_total,
        )
        return True

    def increment_attempts(self, rental_id: str) -> None:
        """
        Увеличивает счётчик попыток взыскания долга
        и обновляет last_attempt_at.
        """
        debt = self.get_by_rental_id(rental_id)
        if not debt:
            logger.debug(
                "increment_attempts called for rental {} but no debt row exists",
                rental_id,
            )
            return

        debt.attempts = (debt.attempts or 0) + 1
        debt.last_attempt_at = datetime.now(timezone.utc)

        logger.debug(
            "Incremented attempts for rental {}: attempts={}, last_attempt_at={}",
            rental_id,
            debt.attempts,
            debt.last_attempt_at,
        )

    # --- Логика ретраев (то, что ломалось в тесте) ---

    def should_retry_debt(self, rental_id: str, backoff_seconds: int) -> bool:
        """
        Логика под тесты:

        - нет долга или долг 0 → не ретраим (False)
        - last_attempt_at is None → ещё ни разу не пытались → True
        - иначе ретраим только если прошло >= backoff_seconds секунд
        """
        debt = self.get_by_rental_id(rental_id)

        if not debt or debt.amount_total <= 0:
            logger.debug(
                "should_retry_debt: rental={} has no positive debt; retry=False",
                rental_id,
            )
            return False

        if not debt.last_attempt_at:
            logger.debug(
                "should_retry_debt: rental={} has never been attempted; retry=True",
                rental_id,
            )
            return True

        now = datetime.now(timezone.utc)
        delta_sec = (now - debt.last_attempt_at).total_seconds()
        retry = delta_sec >= backoff_seconds

        logger.debug(
            "should_retry_debt: rental={} amount={} delta_sec={} backoff={} retry={}",
            rental_id,
            debt.amount_total,
            int(delta_sec),
            backoff_seconds,
            retry,
        )

        return retry

    # --- Привязка долга к конкретной операции/моменту ---

    def attach_debt(self, rental_id: str, amount: int, now: datetime) -> None:
        """
        Используется, когда надо «подвесить» долг за конкретную операцию.
        (Например, биллинг не смог списать оплату за тик.)
        """
        debt = self.get_by_rental_id(rental_id)

        if debt:
            debt.amount_total += amount
            debt.updated_at = now
            logger.debug(
                "attach_debt: updated rental {}: +{} (total={})",
                rental_id,
                amount,
                debt.amount_total,
            )
        else:
            debt = Debt(
                rental_id=rental_id,
                amount_total=amount,
                updated_at=now,
                attempts=0,
                last_attempt_at=None,
            )
            self.session.add(debt)
            logger.debug(
                "attach_debt: created rental {} with amount {}",
                rental_id,
                amount,
            )

        self.session.flush()

    # --- Агрегаты для метрик ---

    def get_total_debt_amount(self) -> int:
        """
        Суммарный долг по всем арендам — нужно для gauge-метрики биллинга.
        """
        total = self.session.query(
            func.coalesce(func.sum(Debt.amount_total), 0)
        ).scalar()
        return int(total or 0)
