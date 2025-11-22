from datetime import datetime, timezone
from typing import Tuple

from loguru import logger

from rental_core.clients.external import ExternalClient
from rental_core.db.repositories.debt import DebtRepository


class PaymentService:
    def __init__(self, debt_repo: DebtRepository, external_client: ExternalClient):
        self.debt_repo = debt_repo
        self.external_client = external_client

    def hold_money_with_fallback(
        self, user_id: str, order_id: str, amount: int
    ) -> None:
        success, error = self.external_client.hold_money_for_order(
            user_id, order_id, amount
        )

        if not success:
            logger.warning(
                f"Payment hold failed for order {order_id}, creating debt: {error}"
            )
            now = datetime.now(timezone.utc)
            self.debt_repo.attach_debt(order_id, amount, now)

    def clear_money_with_fallback(
        self, user_id: str, order_id: str, amount: int
    ) -> Tuple[bool, str]:
        success, error = self.external_client.clear_money_for_order(
            user_id, order_id, amount
        )

        if not success:
            logger.warning(f"Payment clear failed for order {order_id}: {error}")
            return False, error or "Payment service unavailable"

        return True, ""
