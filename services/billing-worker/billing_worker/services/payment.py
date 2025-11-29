from loguru import logger

from billing_worker.clients.external import ExternalClient
from billing_worker.db.repositories.payment import PaymentRepository
from billing_worker.db.repositories.rental import RentalRepository


class PaymentService:
    def __init__(
        self,
        payment_repo: PaymentRepository,
        rental_repo: RentalRepository,
        external_client: ExternalClient,
    ):
        self._payment_repo = payment_repo
        self._rental_repo = rental_repo
        self._external_client = external_client

    def try_charge_rental(self, rental_id: str, amount: int) -> tuple[bool, str | None]:
        if amount <= 0:
            return True, None

        # Get rental info
        rental = self._rental_repo.get_by_id(rental_id)
        if not rental:
            error_msg = f"Rental {rental_id} not found"
            logger.error(error_msg)
            return False, error_msg

        # Try to charge via external service
        success, error = self._external_client.clear_money_for_order(
            rental.user_id, rental_id, amount
        )

        # Record payment attempt
        self._payment_repo.create_payment_attempt(
            rental_id=rental_id, amount=amount, success=success, error=error
        )

        # Update rental total amount if successful
        if success:
            self._rental_repo.update_total_amount(rental_id, amount)
            logger.info(f"Successfully charged {amount} for rental {rental_id}")
        else:
            logger.warning(f"Failed to charge {amount} for rental {rental_id}: {error}")

        return success, error

    def get_total_paid(self, rental_id: str) -> int:
        return self._payment_repo.get_total_paid(rental_id)

    def get_payment_history(self, rental_id: str):
        return self._payment_repo.get_payment_attempts(rental_id)
