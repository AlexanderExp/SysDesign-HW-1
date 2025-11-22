from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.db.models import PaymentAttempt


class PaymentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_payment_attempt(
        self, rental_id: str, amount: int, success: bool, error: str = None
    ) -> PaymentAttempt:
        attempt = PaymentAttempt(
            rental_id=rental_id,
            amount=amount,
            success=success,
            error=error,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(attempt)

        status = "SUCCESS" if success else "FAILED"
        logger.info(f"Payment attempt {status}: rental={rental_id}, amount={amount}")
        if error:
            logger.warning(f"Payment error for rental {rental_id}: {error}")

        return attempt

    def get_total_paid(self, rental_id: str) -> int:
        total = (
            self.session.query(func.coalesce(func.sum(PaymentAttempt.amount), 0))
            .filter(
                PaymentAttempt.rental_id == rental_id, PaymentAttempt.success.is_(True)
            )
            .scalar()
        )
        return total or 0

    def get_payment_attempts(self, rental_id: str) -> list[PaymentAttempt]:
        return (
            self.session.query(PaymentAttempt)
            .filter(PaymentAttempt.rental_id == rental_id)
            .order_by(PaymentAttempt.created_at.desc())
            .all()
        )

    def get_successful_payments(self, rental_id: str) -> list[PaymentAttempt]:
        return (
            self.session.query(PaymentAttempt)
            .filter(
                PaymentAttempt.rental_id == rental_id, PaymentAttempt.success.is_(True)
            )
            .order_by(PaymentAttempt.created_at.desc())
            .all()
        )
