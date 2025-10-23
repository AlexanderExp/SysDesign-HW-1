# services/billing-worker/main.py
import os
import time
import requests
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import create_engine, select, func, update, text, inspect as sqla_inspect
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Text, Boolean

DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://app:app@db:5432/rental")
EXTERNAL_BASE = os.getenv("EXTERNAL_BASE", "http://external-stubs:3629")
TICK_SEC = int(os.getenv("BILLING_TICK_SEC", "30"))
R_BUYOUT = int(os.getenv("R_BUYOUT", "5000"))

# Настройки ретрая долгов
DEBT_CHARGE_STEP = int(os.getenv("DEBT_CHARGE_STEP", "100")
                       )         # порция списания долга
# базовый интервал (экспон. бэкофф)
DEBT_RETRY_BASE_SEC = int(os.getenv("DEBT_RETRY_BASE_SEC", "60"))
DEBT_RETRY_MAX_SEC = int(
    os.getenv("DEBT_RETRY_MAX_SEC", "3600"))    # потолок окна

# ------------- HTTP -------------
_s = requests.Session()
_s.headers.update({"User-Agent": "billing-worker/1.0"})
_s.timeout = float(os.getenv("HTTP_TIMEOUT_SEC", "1.5"))


def _post(path: str, payload: dict):
    r = _s.post(f"{EXTERNAL_BASE.rstrip('/')}/{path.lstrip('/')}",
                json=payload, timeout=_s.timeout)
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
    finished_at: Mapped[Optional[datetime]] = mapped_column(
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
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Debt(Base):
    __tablename__ = "debts"
    rental_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    amount_total: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True)


engine = create_engine(DB_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False,
                            autocommit=False, expire_on_commit=False, future=True)


def _ensure_columns_if_missing() -> None:
    insp = sqla_inspect(engine)
    with engine.begin() as conn:
        cols = {c["name"] for c in insp.get_columns("debts")}
        if "attempts" not in cols:
            conn.execute(
                text("ALTER TABLE debts ADD COLUMN attempts INTEGER DEFAULT 0"))
        if "last_attempt_at" not in cols:
            conn.execute(
                text("ALTER TABLE debts ADD COLUMN last_attempt_at TIMESTAMP"))


def ensure_schema() -> None:
    try:
        PaymentAttempt.__table__.create(bind=engine, checkfirst=True)
        Debt.__table__.create(bind=engine, checkfirst=True)
        _ensure_columns_if_missing()
        print("[billing-worker] schema ensured (payment_attempts, debts)", flush=True)
    except Exception as e:
        print(f"[billing-worker] ensure_schema warning: {e}", flush=True)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _due_amount(price_per_hour: int, free_min: int, started_at: datetime, now: datetime) -> int:
    total_sec = int((_aware(now) - _aware(started_at)).total_seconds())
    billable_sec = max(0, total_sec - free_min * 60)
    return (price_per_hour * billable_sec) // 3600


def _sum_paid(s, rental_id: str) -> int:
    return (
        s.query(func.coalesce(func.sum(PaymentAttempt.amount), 0))
        .filter(PaymentAttempt.rental_id == rental_id, PaymentAttempt.success.is_(True))
        .scalar()
        or 0
    )


def _get_debt_row(s, rental_id: str) -> Optional[Debt]:
    return s.get(Debt, rental_id)


def _get_debt(s, rental_id: str) -> int:
    d = _get_debt_row(s, rental_id)
    return d.amount_total if d else 0


def _add_debt(s, rental_id: str, delta: int) -> None:
    d = _get_debt_row(s, rental_id)
    now = _now()
    if d:
        d.amount_total += delta
        d.updated_at = now
    else:
        s.add(Debt(rental_id=rental_id, amount_total=delta,
              updated_at=now, attempts=0, last_attempt_at=None))


def _try_charge(user_id: str, rental_id: str, amount: int) -> Tuple[bool, Optional[str]]:
    try:
        _post("/clear-money-for-order",
              {"user_id": user_id, "order_id": rental_id, "amount": amount})
        return True, None
    except Exception as e:
        return False, str(e)


def _backoff_window_sec(attempts: int) -> int:
    win = DEBT_RETRY_BASE_SEC * (2 ** min(attempts, 8))
    return min(win, DEBT_RETRY_MAX_SEC)


# <-- добавили алиас, чтобы удовлетворить тест test_backoff_capped -->
def _backoff_seconds(attempts: int) -> int:
    return _backoff_window_sec(attempts)


def _maybe_collect_historical_debt(s, rental: Rental, now: datetime) -> Tuple[int, int]:
    """
    Пытаемся списать исторический долг порцией DEBT_CHARGE_STEP с бэкоффом.
    Возвращаем (charged_delta, debt_delta).
    """
    d = _get_debt_row(s, rental.id)
    if not d or d.amount_total <= 0:
        return 0, 0

    if d.last_attempt_at:
        delta_sec = int(
            (_aware(now) - _aware(d.last_attempt_at)).total_seconds())
        if delta_sec < _backoff_window_sec(d.attempts or 0):
            return 0, 0

    step = min(d.amount_total, DEBT_CHARGE_STEP)
    ok, err = _try_charge(rental.user_id, rental.id, step)

    d.last_attempt_at = _aware(now)

    s.add(
        PaymentAttempt(
            rental_id=rental.id,
            amount=step,
            success=ok,
            error=err,
            created_at=_aware(now),
        )
    )

    if ok:
        # долг уменьшился и общая оплаченная сумма выросла
        d.amount_total -= step
        d.updated_at = _aware(now)
        d.attempts = 0
        rental.total_amount = (rental.total_amount or 0) + \
            step  # <-- ЭТОГО НЕ ХВАТАЛО
        return step, -step
    else:
        d.attempts = (d.attempts or 0) + 1
        return 0, 0


def tick_once():
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

            if due >= R_BUYOUT or (paid + debt) >= R_BUYOUT:
                s.execute(
                    update(Rental)
                    .where(Rental.id == rental.id, Rental.status == "ACTIVE")
                    .values(status="BUYOUT", finished_at=_aware(now))
                )
                s.commit()
                continue

            to_charge = due - paid - debt

            if to_charge >= 1:
                ok, err = _try_charge(rental.user_id, rental.id, to_charge)
                s.add(
                    PaymentAttempt(
                        rental_id=rental.id,
                        amount=to_charge,
                        success=ok,
                        error=err,
                        created_at=_aware(now),
                    )
                )
                if ok:
                    rental.total_amount = (
                        rental.total_amount or 0) + to_charge
                    charged_total += to_charge
                else:
                    debt_total += to_charge
                    _add_debt(s, rental.id, to_charge)

                paid_after = paid + (to_charge if ok else 0)
                debt_after = debt + (0 if ok else to_charge)
                if paid_after + debt_after >= R_BUYOUT:
                    rental.status = "BUYOUT"
                    rental.finished_at = _aware(now)

                s.commit()
                continue

            charged_delta, debt_delta = _maybe_collect_historical_debt(
                s, rental, now)
            charged_total += charged_delta
            debt_total += max(0, debt_delta)
            paid2 = _sum_paid(s, rental.id)
            debt2 = _get_debt(s, rental.id)
            if paid2 + debt2 >= R_BUYOUT:
                rental.status = "BUYOUT"
                rental.finished_at = _aware(now)
            s.commit()

    print(
        f"[billing-worker] tick={TICK_SEC}s R_BUYOUT={R_BUYOUT} active={len(active_ids)} "
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
