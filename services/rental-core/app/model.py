from sqlalchemy.orm import Mapped, mapped_column
from .db import Base
from datetime import datetime, timezone
from dataclasses import dataclass
from sqlalchemy import String, Integer, DateTime, Text, UniqueConstraint, Boolean, func


# Содержит в себе DTO (data transfer objects) / данные, получаемые из внешних источников


@dataclass
class Slot:
    index: int
    empty: bool
    charge: int


@dataclass
class StationData:
    id: str
    tariff_id: str
    location: str
    slots: list[Slot]


@dataclass
class Tariff:
    id: str
    price_per_hour: int
    free_period_min: int
    default_deposit: int


@dataclass
class UserProfile:
    id: str
    has_subscribtion: bool
    trusted: bool


@dataclass
class OfferData:
    id: str
    user_id: str
    station_id: str
    price_per_hour: int
    free_period_min: int
    deposit: int


@dataclass
class OrderData:
    id: str
    user_id: str
    start_station_id: str
    finish_station_id: str
    price_per_hour: int
    free_period_min: int
    deposit: int
    total_amount: int
    start_time: datetime
    finish_time: datetime


class ConfigMap:
    def __init__(self, data: dict):
        self._data = data
        for k, v in data.items():
            self.__setattr__(k, v)

    def __getattr__(self, item):
        return self._data.get(item, None)


@dataclass
class EjectResponse:
    success: bool
    powerbank_id: str

    from sqlalchemy import String, Integer, DateTime, Text, UniqueConstraint, Boolean, func


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    rental_id: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Debt(Base):
    __tablename__ = "debts"
    rental_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    amount_total: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(
        timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
