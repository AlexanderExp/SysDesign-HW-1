import time
from contextlib import contextmanager

from loguru import logger

from billing_worker.clients.external import ExternalClient
from billing_worker.config.logging import setup_logging
from billing_worker.config.settings import Settings
from billing_worker.db.database import get_sessionmaker
from billing_worker.db.repositories.debt import DebtRepository
from billing_worker.db.repositories.payment import PaymentRepository
from billing_worker.db.repositories.rental import RentalRepository
from billing_worker.monitoring.metrics import (
    MetricsCollector,
    init_app_info,
    start_metrics_server,
)
from billing_worker.services.billing import BillingService
from billing_worker.services.debt import DebtService
from billing_worker.services.payment import PaymentService


@contextmanager
def get_services(settings: Settings):
    # TODO: use DI
    sessionmaker = get_sessionmaker(settings)
    session = sessionmaker()
    try:
        rental_repo = RentalRepository(session)
        debt_repo = DebtRepository(session)
        payment_repo = PaymentRepository(session)

        external_client = ExternalClient(settings)

        payment_service = PaymentService(payment_repo, rental_repo, external_client)
        debt_service = DebtService(
            debt_repo, payment_repo, rental_repo, external_client, settings
        )
        billing_service = BillingService(
            rental_repo,
            debt_repo,
            payment_repo,
            payment_service,
            debt_service,
            settings,
        )

        yield billing_service, session
    finally:
        session.close()


def tick_once(settings: Settings):
    start_time = time.time()

    with get_services(settings) as (billing_service, session):
        try:
            result = billing_service.process_all_active_rentals()
            session.commit()

            # Record metrics
            duration = time.time() - start_time
            MetricsCollector.record_billing_cycle(duration, result.active_rentals)

            logger.info(
                f"Billing tick: tick_sec={settings.billing_tick_sec}, "
                f"r_buyout={settings.r_buyout}, "
                f"active={result.active_rentals}, "
                f"charged={result.total_charged}, "
                f"debt_delta={result.total_debt_delta}, "
                f"duration={duration:.2f}s"
            )
        except Exception as e:
            session.rollback()
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
        f"Starting billing worker: tick_sec={settings.billing_tick_sec}, r_buyout={settings.r_buyout}"
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
