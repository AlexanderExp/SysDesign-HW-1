from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Text, UniqueConstraint, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class Rental(Base):
    __tablename__ = "rentals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    powerbank_id: Mapped[str] = mapped_column(String(64))
    price_per_hour: Mapped[int] = mapped_column(Integer)
    free_period_min: Mapped[int] = mapped_column(Integer)
    deposit: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(16))  # ACTIVE / FINISHED / BUYOUT
    total_amount: Mapped[int] = mapped_column(
        Integer, default=0)  # устаревшее поле; для совместимости
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    scope: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(String(64))
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("key", name="uq_idem_key"),)


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    rental_id: Mapped[str] = mapped_column(
        String(64), index=True)  # Хватает index=True
    amount: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))



# явный индекс (на случай конфликтов имён)
Index("ix_payment_attempts_rental_id", PaymentAttempt.rental_id)


class Debt(Base):
    __tablename__ = "debts"
    __table_args__ = {'extend_existing': True}
    rental_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    amount_total: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
