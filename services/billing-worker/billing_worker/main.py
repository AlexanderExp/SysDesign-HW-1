from contextlib import contextmanager
import time

from loguru import logger

from billing_worker.config.settings import Settings
from billing_worker.config.logging import setup_logging
from billing_worker.db.database import (
    get_rental_sessionmaker,
    get_billing_sessionmaker,
)
from billing_worker.db.repositories.rental import RentalRepository
from billing_worker.db.repositories.payment import PaymentRepository
from billing_worker.db.repositories.debt import DebtRepository
from billing_worker.monitoring.metrics import (
    MetricsCollector,
    init_app_info,
    start_metrics_server,
)
from billing_worker.services.billing import BillingService
from billing_worker.services.payment import PaymentService
from billing_worker.services.debt import DebtService
from billing_worker.clients.external import ExternalClient


@contextmanager
def get_services(settings: Settings):
    RentalSessionLocal = get_rental_sessionmaker(settings)
    BillingSessionLocal = get_billing_sessionmaker(settings)

    rental_session = RentalSessionLocal()
    billing_session = BillingSessionLocal()

    try:
        rental_repo = RentalRepository(rental_session)
        payment_repo = PaymentRepository(billing_session)
        debt_repo = DebtRepository(billing_session)

        external = ExternalClient(settings)

        payment_service = PaymentService(
            rental_repo=rental_repo,
            payment_repo=payment_repo,
            external_client=external,
        )
        debt_service = DebtService(
            rental_repo=rental_repo,
            debt_repo=debt_repo,
            payment_repo=payment_repo,
            external_client=external,
            settings=settings,
        )

        billing_service = BillingService(
            rental_repo=rental_repo,
            debt_repo=debt_repo,
            payment_repo=payment_repo,
            payment_service=payment_service,
            debt_service=debt_service,
            settings=settings,
        )

        yield billing_service, rental_session, billing_session

    finally:
        billing_session.close()
        rental_session.close()


def tick_once(settings: Settings):
    start_time = time.time()

    with get_services(settings) as (billing_service, rental_session, billing_session):
        try:
            result = billing_service.process_all_active_rentals()

            rental_session.commit()
            billing_session.commit()

            # Record metrics
            duration = time.time() - start_time
            MetricsCollector.record_billing_cycle(duration, result.active_rentals)

            logger.info(
                "Billing tick: tick_sec={}, r_buyout={}, active={}, charged={}, debt_delta={}",
                settings.billing_tick_sec,
                settings.r_buyout,
                result.active_rentals,
                result.total_charged,
                result.total_debt_delta,
            )
        except Exception as e:
            rental_session.rollback()
            billing_session.rollback()
            MetricsCollector.record_worker_error("billing_cycle_failed")
            logger.error(f"Billing tick failed: {e}")
            raise


def main():
    settings = Settings()
    setup_logging()

    # Start Prometheus metrics server
    start_metrics_server(8001)
    init_app_info("1.0.0")

    logger.info(
        "Starting billing worker: tick_sec={}, r_buyout={}",
        settings.billing_tick_sec,
        settings.r_buyout,
    )
    logger.info("Metrics server started on port 8001")

    while True:
        try:
            tick_once(settings)
        except Exception as e:
            MetricsCollector.record_worker_error("tick_error")
            logger.error(f"Tick error: {e}")

        time.sleep(settings.billing_tick_sec)


if __name__ == "__main__":
    main()
