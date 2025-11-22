from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from shared.db.models import Debt


class DebtRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_rental_id(self, rental_id: str) -> Optional[Debt]:
        return self.session.get(Debt, rental_id)

    def get_amount(self, rental_id: str) -> int:
        debt = self.get_by_rental_id(rental_id)
        return debt.amount_total if debt else 0

    def add_debt(self, rental_id: str, amount: int) -> None:
        debt = self.get_by_rental_id(rental_id)
        now = datetime.now(timezone.utc)

        if debt:
            debt.amount_total += amount
            debt.updated_at = now
            logger.debug(
                f"Updated debt for rental {rental_id}: +{amount} (total: {debt.amount_total})"
            )
        else:
            new_debt = Debt(
                rental_id=rental_id,
                amount_total=amount,
                updated_at=now,
                attempts=0,
                last_attempt_at=None,
            )
            self.session.add(new_debt)
            logger.debug(f"Created new debt for rental {rental_id}: {amount}")

    def reduce_debt(self, rental_id: str, amount: int) -> bool:
        """Reduce debt amount.

        Returns:
            bool: True if debt was reduced, False if not enough debt
        """
        debt = self.get_by_rental_id(rental_id)
        if not debt or debt.amount_total < amount:
            return False

        debt.amount_total -= amount
        debt.updated_at = datetime.now(timezone.utc)
        debt.attempts = 0  # Reset attempts on successful payment
        logger.debug(
            f"Reduced debt for rental {rental_id}: -{amount} (remaining: {debt.amount_total})"
        )
        return True

    def increment_attempts(self, rental_id: str) -> None:
        debt = self.get_by_rental_id(rental_id)
        if debt:
            debt.attempts = (debt.attempts or 0) + 1
            debt.last_attempt_at = datetime.now(timezone.utc)
            logger.debug(
                f"Incremented attempts for rental {rental_id}: {debt.attempts}"
            )

    def should_retry_debt(self, rental_id: str, backoff_seconds: int) -> bool:
        debt = self.get_by_rental_id(rental_id)
        if not debt or debt.amount_total <= 0:
            return False

        if not debt.last_attempt_at:
            return True

        now = datetime.now(timezone.utc)
        delta_sec = int((now - debt.last_attempt_at).total_seconds())
        return delta_sec >= backoff_seconds

    def attach_debt(self, rental_id: str, amount: int, now: datetime) -> None:
        debt = self.get_by_rental_id(rental_id)

        if debt:
            debt.amount_total += amount
            debt.updated_at = now
        else:
            new_debt = Debt(
                rental_id=rental_id,
                amount_total=amount,
                updated_at=now,
                attempts=0,
                last_attempt_at=None,
            )
            self.session.add(new_debt)
        self.session.flush()
