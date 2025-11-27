from datetime import datetime, timezone

from loguru import logger

from rental_core.clients.external import ExternalClient
from rental_core.core.exceptions import EjectFailedException, RentalNotFoundException
from rental_core.core.utils import uuid4
from rental_core.db.models import Rental
from rental_core.db.repositories.debt import DebtRepository
from rental_core.db.repositories.idempotency import IdempotencyRepository
from rental_core.db.repositories.rental import RentalRepository
from rental_core.schemas import (
    RentalStatusResponse,
    StartRentalRequest,
    StopRentalRequest,
)
from rental_core.services.payment import PaymentService
from rental_core.services.quote import QuoteService


class RentalService:
    def __init__(
        self,
        rental_repo: RentalRepository,
        debt_repo: DebtRepository,
        idempotency_repo: IdempotencyRepository,
        quote_service: QuoteService,
        payment_service: PaymentService,
        external_client: ExternalClient,
    ):
        self.rental_repo = rental_repo
        self.debt_repo = debt_repo
        self.idempotency_repo = idempotency_repo
        self.quote_service = quote_service
        self.payment_service = payment_service
        self.external_client = external_client

    def start_rental(
        self, request: StartRentalRequest, idempotency_key: str
    ) -> RentalStatusResponse:
        logger.info(
            f"Starting rental with quote {request.quote_id}, idempotency key: {idempotency_key}"
        )

        cached_response = self.idempotency_repo.get_cached_response(idempotency_key)
        if cached_response:
            logger.info(
                f"Returning cached response for idempotency key: {idempotency_key}"
            )
            return RentalStatusResponse(**cached_response)

        quote = self.quote_service.get_and_validate_quote(request.quote_id)

        eject_response = self.external_client.eject_powerbank(quote.station_id)
        if not eject_response.success:
            logger.error(f"Failed to eject powerbank from station {quote.station_id}")
            raise EjectFailedException()

        now = datetime.now(timezone.utc)
        rental = Rental(
            id=uuid4(),
            user_id=quote.user_id,
            powerbank_id=eject_response.powerbank_id,
            price_per_hour=quote.price_per_hour,
            free_period_min=quote.free_period_min,
            deposit=quote.deposit,
            status="ACTIVE",
            total_amount=0,
            started_at=now,
        )

        self.rental_repo.create_rental(rental)

        self.payment_service.hold_money_with_fallback(
            rental.user_id, rental.id, rental.deposit
        )

        debt_amount = self.debt_repo.get_debt_amount(rental.id)

        response_data = {
            "order_id": rental.id,
            "status": rental.status,
            "powerbank_id": rental.powerbank_id,
            "total_amount": rental.total_amount,
            "debt": debt_amount,
        }

        self.idempotency_repo.create_idempotency_key(
            key=idempotency_key,
            scope="start",
            user_id=rental.user_id,
            response_data=response_data,
        )

        self.quote_service.consume_quote(request.quote_id)

        logger.info(f"Rental {rental.id} started successfully")
        return RentalStatusResponse(**response_data)

    def stop_rental(self, order_id: str, request: StopRentalRequest) -> RentalStatusResponse:
        logger.info(f"Stopping rental {order_id} at station {request.station_id}")

        rental = self.rental_repo.get_rental(order_id)
        if not rental:
            logger.error(f"Rental {order_id} not found")
            raise RentalNotFoundException()

        current_debt = self.debt_repo.get_debt_amount(order_id)

        if rental.status == "FINISHED":
            logger.info(f"Rental {order_id} already finished")
            return RentalStatusResponse(
                order_id=rental.id,
                status=rental.status,
                powerbank_id=rental.powerbank_id,
                total_amount=rental.total_amount,
                debt=current_debt,
            )

        rental.status = "FINISHED"
        rental.finished_at = datetime.now(timezone.utc)
        self.rental_repo.update_rental(rental)

        success, error = self.payment_service.clear_money_with_fallback(
            rental.user_id, rental.id, rental.total_amount
        )

        if not success:
            logger.warning(f"Payment clear failed for rental {order_id}: {error}")

        final_debt = self.debt_repo.get_debt_amount(order_id)

        logger.info(f"Rental {order_id} stopped successfully")
        return RentalStatusResponse(
            order_id=rental.id,
            status=rental.status,
            powerbank_id=rental.powerbank_id,
            total_amount=rental.total_amount,
            debt=final_debt,
        )

    def get_rental_status(self, order_id: str) -> RentalStatusResponse:
        rental = self.rental_repo.get_rental(order_id)
        if not rental:
            logger.error(f"Rental {order_id} not found")
            raise RentalNotFoundException()

        debt_amount = self.debt_repo.get_debt_amount(order_id)

        return RentalStatusResponse(
            order_id=rental.id,
            status=rental.status,
            powerbank_id=rental.powerbank_id,
            total_amount=rental.total_amount,
            debt=debt_amount,
        )
