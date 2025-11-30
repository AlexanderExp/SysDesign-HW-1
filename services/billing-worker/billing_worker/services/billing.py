from datetime import datetime, timezone

from loguru import logger

from billing_worker.config.settings import Settings
from billing_worker.db.repositories.debt import DebtRepository
from billing_worker.db.repositories.payment import PaymentRepository
from billing_worker.db.repositories.rental import RentalRepository
from billing_worker.monitoring.metrics import MetricsCollector, debt_amount_gauge
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

    # ---------- Биллинг одной аренды ----------

    def process_rental_billing(
        self, rental_id: str, current_time: datetime
    ) -> RentalBillingResult:
        rental = self._rental_repo.get_by_id(rental_id)
        if not rental or rental.status != "ACTIVE":
            return RentalBillingResult(charged_amount=0, debt_delta=0)

        # Сколько "теоретически" должно быть начислено за всё время аренды
        due_amount = self._rental_repo.calculate_due_amount(rental, current_time)

        # Уже оплачено и уже висит в долгах
        paid_amount = self._payment_service.get_total_paid(rental_id)
        debt_amount = self._debt_service.get_debt_amount(rental_id)
        exposure = paid_amount + debt_amount

        logger.debug(
            "Rental {}: due={}, paid={}, debt={}, exposure={}, r_buyout={}",
            rental_id,
            due_amount,
            paid_amount,
            debt_amount,
            exposure,
            self._r_buyout,
        )

        # Если уже добили до порога выкупа — просто помечаем buyout и выходим
        if exposure >= self._r_buyout:
            self._rental_repo.set_buyout_status(rental_id)
            logger.info(
                "Buyout already reached for rental {} (paid={}, debt={})",
                rental_id,
                paid_amount,
                debt_amount,
            )
            return RentalBillingResult(charged_amount=0, debt_delta=0)

        charged_amount = 0
        debt_delta = 0

        # Сколько НОВОГО usage надо выставить в этом тике:
        # всё, что должно быть начислено, минус уже учтённое (оплаты + долги)
        new_usage = max(0, due_amount - exposure)

        # но не больше, чем осталось до buyout
        remaining_to_buyout = max(0, self._r_buyout - exposure)
        to_charge = min(new_usage, remaining_to_buyout)

        # 1. Пытаемся списать новый usage
        if to_charge > 0:
            success, error = self._payment_service.try_charge_rental(
                rental_id, to_charge
            )
            MetricsCollector.record_payment_attempt(success, to_charge)

            if success:
                charged_amount += to_charge
                paid_amount += to_charge
                exposure += to_charge
                logger.info(
                    "Charged {} for rental {} (paid={}, debt={})",
                    to_charge,
                    rental_id,
                    paid_amount,
                    debt_amount,
                )
            else:
                # Переводим сумму в долг (сам DebtService внутри обновляет свои метрики)
                self._debt_service.add_debt(rental_id, to_charge)
                debt_delta += to_charge
                debt_amount += to_charge
                exposure += to_charge
                logger.warning(
                    "Failed to charge {} for rental {}, added to debt "
                    "(paid={}, debt={}): {}",
                    to_charge,
                    rental_id,
                    paid_amount,
                    debt_amount,
                    error,
                )

        # 2. Если нового usage нет (или уже всё до buyout), пробуем забрать исторический долг
        if to_charge == 0:
            debt_charged, debt_change = self._debt_service.try_collect_historical_debt(
                rental_id
            )
            if debt_charged or debt_change:
                charged_amount += debt_charged
                debt_delta += debt_change  # может быть отрицательным
                paid_amount += debt_charged
                debt_amount += debt_change
                exposure += debt_charged + debt_change

                logger.info(
                    "Collected {} from historical debt for rental {} "
                    "(debt_delta={}, paid={}, debt={})",
                    debt_charged,
                    rental_id,
                    debt_change,
                    paid_amount,
                    debt_amount,
                )

                if debt_charged > 0:
                    MetricsCollector.record_payment_attempt(True, debt_charged)

        # Финальный чек на buyout после всех изменений
        if exposure >= self._r_buyout:
            self._rental_repo.set_buyout_status(rental_id)
            logger.info(
                "Rental {} reached buyout after tick (paid={}, debt={})",
                rental_id,
                paid_amount,
                debt_amount,
            )

        return RentalBillingResult(
            charged_amount=charged_amount,
            debt_delta=debt_delta,
        )

    # ---------- Агрегат по всем активным арендам ----------

    def _get_total_debt_amount(self) -> int:
        """
        Суммарный долг по всем арендам для gauge-метрики.
        """
        return self._debt_repo.get_total_debt_amount()

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
            except Exception as e:  # noqa: BLE001
                MetricsCollector.record_worker_error("rental_processing_error")
                logger.error("Error processing rental {}: {}", rental_id, e)

        # Обновляем gauge по общему долгу
        try:
            total_debt = self._get_total_debt_amount()
            debt_amount_gauge.set(total_debt)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to update total debt gauge: {}", e)

        logger.info(
            "Billing tick completed: active_rentals={}, charged={}, debt_delta={}",
            len(active_rental_ids),
            total_charged,
            total_debt_delta,
        )

        return AllRentalsBillingResult(
            active_rentals=len(active_rental_ids),
            total_charged=total_charged,
            total_debt_delta=total_debt_delta,
        )
