from fastapi import HTTPException


class RentalCoreException(Exception):
    """Base exception for rental core service."""

    pass


class QuoteNotFoundException(RentalCoreException):
    """Quote not found or expired."""

    pass


class QuoteExpiredException(RentalCoreException):
    """Quote has expired."""

    pass


class RentalNotFoundException(RentalCoreException):
    """Rental not found."""

    pass


class EjectFailedException(RentalCoreException):
    """Failed to eject powerbank."""

    pass


class PaymentFailedException(RentalCoreException):
    """Payment operation failed."""

    pass


class IdempotencyKeyMissingException(RentalCoreException):
    """Idempotency key is missing."""

    pass


def quote_not_found_exception():
    return HTTPException(status_code=400, detail="invalid or expired quote")


def quote_expired_exception():
    return HTTPException(status_code=400, detail="quote expired")


def rental_not_found_exception():
    return HTTPException(status_code=404, detail="order not found")


def eject_failed_exception():
    return HTTPException(status_code=409, detail="no free slots / eject failed")


def idempotency_key_missing_exception():
    return HTTPException(status_code=400, detail="missing Idempotency-Key")
