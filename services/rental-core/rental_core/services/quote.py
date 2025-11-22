from datetime import datetime, timedelta, timezone

from loguru import logger

from rental_core.clients.external import ExternalClient
from rental_core.core.exceptions import QuoteExpiredException, QuoteNotFoundException
from rental_core.core.utils import uuid4
from rental_core.db.repositories.quote import QuoteRepository
from rental_core.schemas import QuoteData, QuoteRequest, QuoteResponse


class QuoteService:
    def __init__(self, quote_repo: QuoteRepository, external_client: ExternalClient):
        self.quote_repo = quote_repo
        self.external_client = external_client

    def create_quote(self, request: QuoteRequest) -> QuoteResponse:
        logger.info(
            f"Creating quote for user {request.user_id}, station {request.station_id}"
        )

        station_data = self.external_client.get_station_data(request.station_id)
        tariff = self.external_client.get_tariff(station_data.tariff_id)
        user = self.external_client.get_user_profile(request.user_id)

        price_per_hour = tariff.price_per_hour
        free_min = tariff.free_period_min
        deposit = (
            tariff.default_deposit
            if not user.trusted
            else max(0, tariff.default_deposit // 2)
        )

        now = datetime.now(timezone.utc)
        quote_id = uuid4()
        expires_at = now.replace(microsecond=0) + timedelta(seconds=60)

        self.quote_repo.create_quote(
            quote_id=quote_id,
            user_id=request.user_id,
            station_id=request.station_id,
            price_per_hour=price_per_hour,
            free_period_min=free_min,
            deposit=deposit,
            expires_at=expires_at,
            created_at=now,
        )

        logger.info(f"Quote {quote_id} created successfully")

        return QuoteResponse(
            quote_id=quote_id,
            user_id=request.user_id,
            station_id=request.station_id,
            price_per_hour=price_per_hour,
            free_period_min=free_min,
            deposit=deposit,
            expires_in_sec=60,
        )

    def get_and_validate_quote(self, quote_id: str) -> QuoteData:
        quote = self.quote_repo.get_quote(quote_id)
        if not quote:
            logger.warning(f"Quote {quote_id} not found")
            raise QuoteNotFoundException()

        expires_at = quote.expires_at
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at)
            except Exception:
                expires_at = None

        if isinstance(expires_at, datetime):
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                logger.warning(f"Quote {quote_id} has expired")
                raise QuoteExpiredException()

        return quote

    def consume_quote(self, quote_id: str) -> None:
        self.quote_repo.delete_quote(quote_id)
        logger.debug(f"Quote {quote_id} consumed")
