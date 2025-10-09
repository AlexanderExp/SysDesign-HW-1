from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from .db import Base


class Rental(Base):
    __tablename__ = "rentals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    powerbank_id: Mapped[str] = mapped_column(String(64), index=True)
    price_per_hour: Mapped[int] = mapped_column(Integer)
    free_period_min: Mapped[int] = mapped_column(Integer)
    deposit: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(
        String(16), index=True, default="active")  # active|finished|buyout
    total_amount: Mapped[int] = mapped_column(Integer, default=0)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
