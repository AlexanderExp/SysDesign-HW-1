from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from rental_core.clients.external import ExternalClient
from rental_core.config.settings import Settings
from rental_core.core.exceptions import idempotency_key_missing_exception
from rental_core.db.database import get_sessionmaker
from rental_core.db.repositories.debt import DebtRepository
from rental_core.db.repositories.idempotency import IdempotencyRepository
from rental_core.db.repositories.quote import QuoteRepository
from rental_core.db.repositories.rental import RentalRepository
from rental_core.services.payment import PaymentService
from rental_core.services.quote import QuoteService
from rental_core.services.rental import RentalService


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def get_session(settings: Settings = Depends(get_settings)) -> Session:
    sessionmaker = get_sessionmaker(settings)
    session = sessionmaker()
    try:
        yield session
    finally:
        session.close()


def get_external_client(request: Request) -> ExternalClient:
    return request.app.state.external_client


def get_quote_repository(session: Session = Depends(get_session)) -> QuoteRepository:
    return QuoteRepository(session)


def get_rental_repository(session: Session = Depends(get_session)) -> RentalRepository:
    return RentalRepository(session)


def get_debt_repository(session: Session = Depends(get_session)) -> DebtRepository:
    return DebtRepository(session)


def get_idempotency_repository(
    session: Session = Depends(get_session),
) -> IdempotencyRepository:
    return IdempotencyRepository(session)


def get_quote_service(
    quote_repo: QuoteRepository = Depends(get_quote_repository),
    request: Request = None,
) -> QuoteService:
    external_client = request.app.state.external_client
    return QuoteService(quote_repo, external_client)


def get_payment_service(
    debt_repo: DebtRepository = Depends(get_debt_repository),
    request: Request = None,
) -> PaymentService:
    external_client = request.app.state.external_client
    return PaymentService(debt_repo, external_client)


def get_rental_service(
    rental_repo: RentalRepository = Depends(get_rental_repository),
    debt_repo: DebtRepository = Depends(get_debt_repository),
    idempotency_repo: IdempotencyRepository = Depends(get_idempotency_repository),
    quote_service: QuoteService = Depends(get_quote_service),
    payment_service: PaymentService = Depends(get_payment_service),
    request: Request = None,
) -> RentalService:
    external_client = request.app.state.external_client
    return RentalService(
        rental_repo,
        debt_repo,
        idempotency_repo,
        quote_service,
        payment_service,
        external_client,
    )


def get_idempotency_key(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> str:
    if not idempotency_key:
        raise idempotency_key_missing_exception()
    return idempotency_key
