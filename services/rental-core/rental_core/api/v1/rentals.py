from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from rental_core.api.dependencies import (
    get_idempotency_key,
    get_quote_service,
    get_rental_service,
    get_session,
)
from rental_core.core.exceptions import (
    EjectFailedException,
    QuoteExpiredException,
    QuoteNotFoundException,
    RentalNotFoundException,
    eject_failed_exception,
    quote_expired_exception,
    quote_not_found_exception,
    rental_not_found_exception,
)
from rental_core.schemas import (
    QuoteRequest,
    QuoteResponse,
    RentalStatusResponse,
    StartRentalRequest,
    StopRentalRequest,
)
from rental_core.services.quote import QuoteService
from rental_core.services.rental import RentalService

router = APIRouter()


@router.post("/rentals/quote", response_model=QuoteResponse)
def create_quote(
    request: QuoteRequest,
    quote_service: QuoteService = Depends(get_quote_service),
    session: Session = Depends(get_session),
):
    try:
        response = quote_service.create_quote(request)
        session.commit()
        return response
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rentals/start", response_model=RentalStatusResponse)
def start_rental(
    request: StartRentalRequest,
    idempotency_key: str = Depends(get_idempotency_key),
    rental_service: RentalService = Depends(get_rental_service),
    session: Session = Depends(get_session),
):
    from loguru import logger

    try:
        response = rental_service.start_rental(request, idempotency_key)
        session.commit()
        return response
    except QuoteNotFoundException:
        session.rollback()
        raise quote_not_found_exception()
    except QuoteExpiredException:
        session.rollback()
        raise quote_expired_exception()
    except EjectFailedException:
        session.rollback()
        raise eject_failed_exception()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error starting rental: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rentals/{order_id}/stop", response_model=RentalStatusResponse)
def stop_rental(
    order_id: str,
    request: StopRentalRequest,
    rental_service: RentalService = Depends(get_rental_service),
    session: Session = Depends(get_session),
):
    try:
        response = rental_service.stop_rental(order_id, request)
        session.commit()
        return response
    except RentalNotFoundException:
        session.rollback()
        raise rental_not_found_exception()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rentals/{order_id}/status", response_model=RentalStatusResponse)
def get_rental_status(
    order_id: str,
    rental_service: RentalService = Depends(get_rental_service),
):
    try:
        return rental_service.get_rental_status(order_id)
    except RentalNotFoundException:
        raise rental_not_found_exception()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
