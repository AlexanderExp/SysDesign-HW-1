from loguru import logger

from billing_worker.clients.external import ExternalClient
from billing_worker.config.settings import Settings
from billing_worker.db.repositories.debt import DebtRepository
from billing_worker.db.repositories.payment import PaymentRepository
from billing_worker.db.repositories.rental import RentalRepository


class DebtService:
    """Service for debt management and retry logic."""

    def __init__(
        self,
        debt_repo: DebtRepository,
        payment_repo: PaymentRepository,
        rental_repo: RentalRepository,
        external_client: ExternalClient,
        settings: Settings,
    ):
        self._debt_repo = debt_repo
        self._payment_repo = payment_repo
        self._rental_repo = rental_repo
        self._external_client = external_client
        self._debt_retry_base_sec = settings.debt_retry_base_sec
        self._debt_retry_max_sec = settings.debt_retry_max_sec
        self._debt_charge_step = settings.debt_charge_step

    def calculate_backoff_seconds(self, attempts: int) -> int:
        """Calculate backoff window in seconds using exponential backoff.
        
        Formula: base * 2^attempts, capped at max
        Example: 60 * 2^0=60s, 60 * 2^1=120s, 60 * 2^2=240s, ...
        """
        window = self._debt_retry_base_sec * (2 ** min(attempts, 8))
        return min(window, self._debt_retry_max_sec)

    def try_collect_historical_debt(self, rental_id: str) -> tuple[int, int]:
        """Try to collect historical debt with exponential backoff.

        Args:
            rental_id: Rental ID

        Returns:
            Tuple[int, int]: (charged_amount, debt_delta)
        """
        debt = self._debt_repo.get_by_rental_id(rental_id)
        if not debt or debt.amount_total <= 0:
            return 0, 0

        # Check if we should retry based on backoff
        backoff_seconds = self.calculate_backoff_seconds(debt.attempts or 0)
        if not self._debt_repo.should_retry_debt(rental_id, backoff_seconds):
            logger.debug(f"Debt retry for {rental_id} still in backoff period")
            return 0, 0

        # Calculate charge amount (limited by step size)
        charge_amount = min(debt.amount_total, self._debt_charge_step)

        # Get rental info for user_id
        rental = self._rental_repo.get_by_id(rental_id)
        if not rental:
            logger.error(f"Rental {rental_id} not found for debt collection")
            return 0, 0

        # Try to charge
        success, error = self._external_client.clear_money_for_order(
            rental.user_id, rental_id, charge_amount
        )

        # Record payment attempt
        self._payment_repo.create_payment_attempt(
            rental_id=rental_id, amount=charge_amount, success=success, error=error
        )

        if success:
            # Reduce debt and update rental total
            self._debt_repo.reduce_debt(rental_id, charge_amount)
            self._rental_repo.update_total_amount(rental_id, charge_amount)

            logger.info(
                f"Successfully collected {charge_amount} debt for rental {rental_id}"
            )
            return charge_amount, -charge_amount
        else:
            # Increment retry attempts
            self._debt_repo.increment_attempts(rental_id)
            logger.warning(f"Failed to collect debt for rental {rental_id}: {error}")
            return 0, 0

    def add_debt(self, rental_id: str, amount: int) -> None:
        """Add debt for rental."""
        self._debt_repo.add_debt(rental_id, amount)
        logger.info(f"Added debt {amount} for rental {rental_id}")

    def get_debt_amount(self, rental_id: str) -> int:
        """Get current debt amount for rental."""
        return self._debt_repo.get_amount(rental_id)
