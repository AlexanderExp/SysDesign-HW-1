from pydantic import BaseModel, Field
from typing import Optional


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


class StartRequest(BaseModel):
    quote_id: str


class OrderStatus(BaseModel):
    order_id: str
    status: str
    powerbank_id: Optional[str] = None
    total_amount: int
