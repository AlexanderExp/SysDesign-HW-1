from datetime import datetime, timezone

from loguru import logger

from billing_worker.config.settings import Settings
from billing_worker.db.repositories.debt import DebtRepository
from billing_worker.db.repositories.payment import PaymentRepository
from billing_worker.db.repositories.rental import RentalRepository
from billing_worker.schemas import AllRentalsBillingResult, RentalBillingResult
from billing_worker.services.debt import DebtService
from billing_worker.services.payment import PaymentService


class BillingService:
    def __init__(
        self,
        rental_repo: RentalRepository,
        debt_repo: DebtRepository,
        payment_repo: PaymentRepository,
        payment_service: PaymentService,
        debt_service: DebtService,
        settings: Settings,
    ):
        self._rental_repo = rental_repo
        self._debt_repo = debt_repo
        self._payment_repo = payment_repo
        self._payment_service = payment_service
        self._debt_service = debt_service
        self._r_buyout = settings.r_buyout

    def process_rental_billing(
        self, rental_id: str, current_time: datetime
    ) -> RentalBillingResult:
        rental = self._rental_repo.get_by_id(rental_id)
        if not rental or rental.status != "ACTIVE":
            return RentalBillingResult(charged_amount=0, debt_delta=0)

        # Calculate amounts
        due_amount = self._rental_repo.calculate_due_amount(rental, current_time)
        paid_amount = self._payment_service.get_total_paid(rental_id)
        debt_amount = self._debt_service.get_debt_amount(rental_id)

        logger.debug(f"Rental {rental_id}: due={due_amount}, paid={paid_amount}, debt={debt_amount}")

        # Check for buyout condition
        if (paid_amount + debt_amount) >= self._r_buyout:
            self._rental_repo.set_buyout_status(rental_id)
            logger.info(f"Buyout reached for rental {rental_id}: {paid_amount + debt_amount}")
            return RentalBillingResult(charged_amount=0, debt_delta=0)

        # Calculate amount to charge
        to_charge = due_amount - paid_amount - debt_amount

        charged_amount = 0
        debt_delta = 0

        # Try to charge new amount if needed
        if to_charge > 0:
            success, error = self._payment_service.try_charge_rental(
                rental_id, to_charge
            )

            if success:
                charged_amount = to_charge
                logger.info(f"Charged {to_charge} for rental {rental_id}")
            else:
                # Add to debt if charge failed
                self._debt_service.add_debt(rental_id, to_charge)
                debt_delta = to_charge
                logger.warning(f"Added debt {to_charge} for rental {rental_id}")

            # Check buyout after payment/debt
            new_paid = paid_amount + (to_charge if success else 0)
            new_debt = debt_amount + (0 if success else to_charge)

            if new_paid + new_debt >= self._r_buyout:
                self._rental_repo.set_buyout_status(rental_id)
                logger.info(
                    f"Rental {rental_id} reached buyout after billing: {new_paid + new_debt}"
                )

        # Try to collect historical debt
        if to_charge < 1:  # Only if we didn't charge new amount
            debt_charged, debt_change = self._debt_service.try_collect_historical_debt(
                rental_id
            )
            charged_amount += debt_charged
            debt_delta += debt_change  # This will be negative if debt was reduced

            # Check buyout after debt collection
            if debt_charged > 0:
                final_paid = self._payment_service.get_total_paid(rental_id)
                final_debt = self._debt_service.get_debt_amount(rental_id)

                if final_paid + final_debt >= self._r_buyout:
                    self._rental_repo.set_buyout_status(rental_id)
                    logger.info(
                        f"Rental {rental_id} reached buyout after debt collection: {final_paid + final_debt}"
                    )

        return RentalBillingResult(
            charged_amount=charged_amount, debt_delta=max(0, debt_delta)
        )

    def process_all_active_rentals(self) -> AllRentalsBillingResult:
        active_rental_ids = self._rental_repo.get_active_rental_ids()
        current_time = datetime.now(timezone.utc)

        total_charged = 0
        total_debt_delta = 0

        for rental_id in active_rental_ids:
            try:
                result = self.process_rental_billing(rental_id, current_time)
                total_charged += result.charged_amount
                total_debt_delta += result.debt_delta
            except Exception as e:
                logger.error(f"Error processing rental {rental_id}: {e}")

        logger.info(
            f"Billing tick completed: "
            f"active_rentals={len(active_rental_ids)}, "
            f"charged={total_charged}, "
            f"debt_delta={total_debt_delta}"
        )

        return AllRentalsBillingResult(
            active_rentals=len(active_rental_ids),
            total_charged=total_charged,
            total_debt_delta=total_debt_delta,
        )
