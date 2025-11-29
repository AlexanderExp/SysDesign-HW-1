from fastapi import HTTPException


class RentalCoreException(Exception):
    pass


class QuoteNotFoundException(RentalCoreException):
    pass


class QuoteExpiredException(RentalCoreException):
    pass


class RentalNotFoundException(RentalCoreException):
    pass


class EjectFailedException(RentalCoreException):
    pass


class PaymentFailedException(RentalCoreException):
    pass


class IdempotencyKeyMissingException(RentalCoreException):
    pass


def quote_not_found_exception():
    return HTTPException(status_code=400, detail="Quote not found")


def quote_expired_exception():
    return HTTPException(status_code=400, detail="Quote has expired")


def rental_not_found_exception():
    return HTTPException(status_code=404, detail="Rental not found")


def eject_failed_exception():
    return HTTPException(status_code=409, detail="Cannot eject powerbank")


def idempotency_key_missing_exception():
    return HTTPException(status_code=400, detail="Idempotency key required")
