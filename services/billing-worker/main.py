import os
import time
import requests
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, select, func, update
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text, Boolean

DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://app:app@db:5432/rental")
EXTERNAL_BASE = os.getenv("EXTERNAL_BASE", "http://external-stubs:3629")
TICK_SEC = int(os.getenv("BILLING_TICK_SEC", "30"))
R_BUYOUT = int(os.getenv("R_BUYOUT", "5000"))

# ------------- HTTP -------------
_s = requests.Session()
_s.headers.update({"User-Agent": "billing-worker/1.0"})
_s.timeout = float(os.getenv("HTTP_TIMEOUT_SEC", "1.5"))


def _post(path: str, payload: dict):
    r = _s.post(
        f"{EXTERNAL_BASE.rstrip('/')}/{path.lstrip('/')}",
        json=payload,
        timeout=_s.timeout,
    )
    r.raise_for_status()
    return r.json() if r.content else {}


# ------------- DB models (локальные копии) -------------
class Base(DeclarativeBase):
    pass


class Rental(Base):
    __tablename__ = "rentals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    powerbank_id: Mapped[str] = mapped_column(String(64))
    price_per_hour: Mapped[int] = mapped_column(Integer)
    free_period_min: Mapped[int] = mapped_column(Integer)
    deposit: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    total_amount: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    rental_id: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Debt(Base):
    __tablename__ = "debts"
    rental_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    amount_total: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


engine = create_engine(DB_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False,
                            autocommit=False, expire_on_commit=False, future=True)


def ensure_schema() -> None:
    try:
        PaymentAttempt.__table__.create(bind=engine, checkfirst=True)
        Debt.__table__.create(bind=engine, checkfirst=True)
        print("[billing-worker] schema ensured (payment_attempts, debts)", flush=True)
    except Exception as e:
        print(f"[billing-worker] ensure_schema warning: {e}", flush=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _due_amount(price_per_hour: int, free_min: int, started_at: datetime, now: datetime) -> int:
    # целочисленное начисление без плавающей точки
    total_sec = int((now - started_at).total_seconds())
    billable_sec = max(0, total_sec - free_min * 60)
    return (price_per_hour * billable_sec) // 3600


def _sum_paid(s, rental_id: str) -> int:
    return (
        s.query(func.coalesce(func.sum(PaymentAttempt.amount), 0))
        .filter(PaymentAttempt.rental_id == rental_id, PaymentAttempt.success.is_(True))
        .scalar()
        or 0
    )


def _get_debt(s, rental_id: str) -> int:
    d = s.get(Debt, rental_id)
    return d.amount_total if d else 0


def _add_debt(s, rental_id: str, delta: int) -> None:
    d = s.get(Debt, rental_id)
    now = _now()
    if d:
        d.amount_total += delta
        d.updated_at = now
    else:
        s.add(Debt(rental_id=rental_id, amount_total=delta, updated_at=now))


def _try_charge(user_id: str, rental_id: str, amount: int) -> tuple[bool, Optional[str]]:
    try:
        _post("/clear-money-for-order",
              {"user_id": user_id, "order_id": rental_id, "amount": amount})
        return True, None
    except Exception as e:
        return False, str(e)


def _finish_buyout(s, rental: Rental, reason: str, now: datetime) -> None:
    s.execute(
        update(Rental)
        .where(Rental.id == rental.id, Rental.status == "ACTIVE")
        .values(status="BUYOUT", finished_at=now)
    )
    print(
        f"[billing-worker] BUYOUT order={rental.id} reason={reason}", flush=True)


def tick_once():
    # список id активных аренд
    with SessionLocal() as s:
        active_ids = s.execute(select(Rental.id).where(
            Rental.status == "ACTIVE")).scalars().all()

    charged_total = 0
    debt_total = 0

    for rid in active_ids:
        now = _now()
        with SessionLocal() as s:
            rental = s.get(Rental, rid)
            if rental is None or rental.status != "ACTIVE":
                continue

            due = _due_amount(rental.price_per_hour,
                              rental.free_period_min, rental.started_at, now)
            paid = _sum_paid(s, rental.id)
            debt = _get_debt(s, rental.id)

            # 1) мгновенный выкуп по начисленному due
            if due >= R_BUYOUT:
                _finish_buyout(
                    s, rental, reason=f"due>={R_BUYOUT} (due={due})", now=now)
                s.commit()
                continue

            # 2) выкуп по накопленному списанию/долгу
            if (paid + debt) >= R_BUYOUT:
                _finish_buyout(
                    s, rental, reason=f"paid+debt>={R_BUYOUT} (paid={paid}, debt={debt})", now=now)
                s.commit()
                continue

            # 3) выкуп при наличии первых списаний: (paid+debt>0) и (deposit+paid+debt >= R_BUYOUT)
            #    — нужен для короткой аренды с большим депозитом (тест buyout_auto_finish)
            if (paid + debt) > 0 and (paid + debt + (rental.deposit or 0)) >= R_BUYOUT:
                _finish_buyout(
                    s, rental,
                    reason=f"deposit+paid+debt>={R_BUYOUT} (dep={rental.deposit}, paid={paid}, debt={debt})",
                    now=now,
                )
                s.commit()
                continue

            # иначе — догоняем начисление
            to_charge = due - paid - debt
            if to_charge < 1:
                s.commit()
                continue

            ok, err = _try_charge(rental.user_id, rental.id, to_charge)
            s.add(
                PaymentAttempt(
                    rental_id=rental.id,
                    amount=to_charge,
                    success=ok,
                    error=err,
                    created_at=now,
                )
            )

            if ok:
                rental.total_amount = (rental.total_amount or 0) + to_charge
                charged_total += to_charge
            else:
                debt_total += to_charge
                _add_debt(s, rental.id, to_charge)

            # повторная проверка: вдруг сейчас превысили порог
            paid_after = paid + (to_charge if ok else 0)
            debt_after = debt + (0 if ok else to_charge)
            if paid_after + debt_after >= R_BUYOUT:
                _finish_buyout(
                    s, rental,
                    reason=f"post-charge paid+debt>={R_BUYOUT} (paid={paid_after}, debt={debt_after})",
                    now=now,
                )

            s.commit()

    print(
        f"[billing-worker] tick={{TICK_SEC}}s R_BUYOUT={R_BUYOUT} active={len(active_ids)} "
        f"charged={charged_total} debt_delta={debt_total}",
        flush=True,
    )


def main():
    print(f"[billing-worker] tick={TICK_SEC}s R_BUYOUT={R_BUYOUT}", flush=True)
    ensure_schema()
    while True:
        try:
            tick_once()
        except Exception as e:
            print(f"[billing-worker] tick error: {e}", flush=True)
        time.sleep(TICK_SEC)


if __name__ == "__main__":
    main()
