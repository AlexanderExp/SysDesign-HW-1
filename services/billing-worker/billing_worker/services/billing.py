from datetime import datetime, timezone

from loguru import logger

from billing_worker.config.settings import Settings
from billing_worker.db.repositories.debt import DebtRepository
from billing_worker.db.repositories.payment import PaymentRepository
from billing_worker.db.repositories.rental import RentalRepository
from billing_worker.monitoring.metrics import MetricsCollector
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

        exposure = paid_amount + debt_amount

        logger.debug(
            "Rental %s: due=%s, paid=%s, debt=%s, exposure=%s, r_buyout=%s",
            rental_id,
            due_amount,
            paid_amount,
            debt_amount,
            exposure,
            self._r_buyout,
        )

        # Already at or above buyout?
        if exposure >= self._r_buyout:
            self._rental_repo.set_buyout_status(rental_id)
            logger.info(
                "Buyout reached for rental %s (paid=%s, debt=%s)",
                rental_id,
                paid_amount,
                debt_amount,
            )
            return RentalBillingResult(charged_amount=0, debt_delta=0)

        remaining_to_buyout = self._r_buyout - exposure
        remaining_usage = max(0, due_amount - exposure)

        # Don't charge more than both "what is really due" and "what's left till buyout"
        to_charge = min(remaining_usage, remaining_to_buyout)

        charged_amount = 0
        debt_delta = 0

        # Try to charge new amount if needed
        if to_charge > 0:
            success, error = self._payment_service.try_charge_rental(
                rental_id, to_charge
            )

            if success:
                charged_amount = to_charge
                MetricsCollector.record_payment_attempt(True, to_charge)
                logger.info(f"Charged {to_charge} for rental {rental_id}")
                paid_amount += to_charge
                exposure += to_charge
                logger.info(
                    "Charged %s for rental %s (paid=%s, debt=%s)",
                    to_charge,
                    rental_id,
                    paid_amount,
                    debt_amount,
                )
            else:
                # Add to debt if charge failed
                self._debt_service.add_debt(rental_id, to_charge)
                debt_delta += to_charge
                debt_amount += to_charge
                exposure += to_charge
                logger.warning(
                    "Added debt %s for rental %s (paid=%s, debt=%s): %s",
                    to_charge,
                    rental_id,
                    paid_amount,
                    debt_amount,
                    error, )
                debt_delta = to_charge
                MetricsCollector.record_payment_attempt(False, to_charge)
                MetricsCollector.record_debt_operation("add", to_charge)
                logger.warning(f"Added debt {to_charge} for rental {rental_id}")

            # Check buyout after payment/debt
            new_paid = paid_amount + (to_charge if success else 0)
            new_debt = debt_amount + (0 if success else to_charge)

            if new_paid + new_debt >= self._r_buyout:
                self._rental_repo.set_buyout_status(rental_id)
                logger.info(
                    f"Rental {rental_id} reached buyout after billing: {new_paid + new_debt}"
                )

        # If we didn't charge new usage, try to collect historical debt
        if to_charge == 0:
            debt_charged, debt_change = self._debt_service.try_collect_historical_debt(
                rental_id
            )
            if debt_charged or debt_change:
                charged_amount += debt_charged
                debt_delta += debt_change  # negative if debt was reduced
                paid_amount += debt_charged
                debt_amount += debt_change
                exposure += debt_charged + debt_change
                logger.info(
                    "Collected %s from historical debt for rental %s (debt_delta=%s)",
                    debt_charged,
                    rental_id,
                    debt_change,
                )

        # Final buyout check after any changes
        if exposure >= self._r_buyout:
            self._rental_repo.set_buyout_status(rental_id)
            logger.info(
                "Rental %s reached buyout after tick (paid=%s, debt=%s)",
                rental_id,
                paid_amount,
                debt_amount,
            )
            if debt_charged > 0:
                MetricsCollector.record_payment_attempt(True, debt_charged)
                MetricsCollector.record_debt_operation("reduce", abs(debt_change))

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
                MetricsCollector.record_worker_error("rental_processing_error")
                logger.error(f"Error processing rental {rental_id}: {e}")

        # Update debt amount gauge with current total
        try:
            total_debt = self._get_total_debt_amount()
            from billing_worker.monitoring.metrics import debt_amount_gauge

            debt_amount_gauge.set(total_debt)
        except Exception as e:
            logger.error(f"Failed to update debt gauge: {e}")

        logger.info(
            "Billing tick completed: active_rentals=%s, charged=%s, debt_delta=%s",
            len(active_rental_ids),
            total_charged,
            total_debt_delta,
        )

        return AllRentalsBillingResult(
            active_rentals=len(active_rental_ids),
            total_charged=total_charged,
            total_debt_delta=total_debt_delta,
        )
