from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class QuoteRequest(BaseModel):
    station_id: str
    user_id: str


class QuoteResponse(BaseModel):
    quote_id: str
    user_id: str
    station_id: str
    price_per_hour: int
    free_period_min: int
    deposit: int
    expires_in_sec: int = Field(60, description="TTL оффера")


class StartRentalRequest(BaseModel):
    quote_id: str


class StopRentalRequest(BaseModel):
    station_id: str


class RentalStatusResponse(BaseModel):
    order_id: str
    status: str
    powerbank_id: Optional[str] = None
    total_amount: int
    debt: int = 0


class HealthResponse(BaseModel):
    ok: bool = True


# Internal schemas for services
class QuoteData(BaseModel):
    id: str
    user_id: str
    station_id: str
    price_per_hour: int
    free_period_min: int
    deposit: int
    expires_at: datetime
    created_at: datetime


class RentalData(BaseModel):
    id: str
    user_id: str
    powerbank_id: str
    price_per_hour: int
    free_period_min: int
    deposit: int
    status: str
    total_amount: int
    started_at: datetime
    finished_at: Optional[datetime] = None


class DebtData(BaseModel):
    rental_id: str
    amount_total: int
    updated_at: datetime
    attempts: int = 0
    last_attempt_at: Optional[datetime] = None
