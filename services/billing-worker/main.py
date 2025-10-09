from sqlalchemy import String, Integer, DateTime, Boolean, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from models import Rental, PaymentAttempt, Debt
import os
import time
import requests
from datetime import datetime, timezone
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://app:app@db:5432/rental")
EXTERNAL_BASE = os.getenv("EXTERNAL_BASE", "http://external-stubs:3629")
TICK_SEC = int(os.getenv("BILLING_TICK_SEC", "30"))   # период списаний
R_BUYOUT = int(os.getenv("R_BUYOUT", "5000"))

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
Session = sessionmaker(bind=engine, autoflush=False,
                       autocommit=False, expire_on_commit=False, future=True)


def accrued_total(now: datetime, r: Rental) -> int:
    """Сколько клиент НАкопил к оплате с начала аренды по текущему тарифу."""
    elapsed = max(0, (now - r.started_at).total_seconds())
    if elapsed <= r.free_period_min * 60:
        return 0
    # минутная тарификация для регулярных списаний
    minutes = int(elapsed // 60) - r.free_period_min
    per_min = r.price_per_hour / 60.0
    return int(minutes * per_min)


def payments_ok_sum(s, rental_id: str) -> int:
    q = select(func.coalesce(func.sum(PaymentAttempt.amount), 0)).where(
        PaymentAttempt.rental_id == rental_id, PaymentAttempt.success == True
    )
    return s.execute(q).scalar_one()


def debt_sum(s, rental_id: str) -> int:
    d = s.get(Debt, rental_id)
    return d.amount_total if d else 0


def add_debt(s, rental_id: str, amount: int):
    d = s.get(Debt, rental_id)
    if not d:
        d = Debt(rental_id=rental_id, amount_total=0,
                 updated_at=datetime.now(timezone.utc))
    d.amount_total += amount
    d.updated_at = datetime.now(timezone.utc)
    s.merge(d)


def try_charge(user_id: str, rental_id: str, amount: int) -> tuple[bool, str | None]:
    try:
        r = requests.post(f"{EXTERNAL_BASE}/clear-money-for-order",
                          json={"user_id": user_id,
                                "order_id": rental_id, "amount": amount},
                          timeout=1.5)
        r.raise_for_status()
        return True, None
    except Exception as e:
        return False, str(e)


def maybe_buyout(s, r: Rental):
    paid = payments_ok_sum(s, r.id)
    debt = debt_sum(s, r.id)
    if paid + debt >= R_BUYOUT and r.status == "active":
        r.status = "buyout"
        r.finished_at = datetime.now(timezone.utc)
        s.add(r)


def tick():
    now = datetime.now(timezone.utc)
    with Session() as s:
        actives = s.execute(select(Rental).where(
            Rental.status == "active")).scalars().all()
        for r in actives:
            acc = accrued_total(now, r)
            paid = payments_ok_sum(s, r.id)
            debt = debt_sum(s, r.id)
            to_charge = acc - paid - debt
            if to_charge <= 0:
                continue

            ok, err = try_charge(r.user_id, r.id, to_charge)
            s.add(PaymentAttempt(rental_id=r.id, amount=to_charge,
                  success=ok, error=err, created_at=now))
            if not ok:
                add_debt(s, r.id, to_charge)

            maybe_buyout(s, r)
        s.commit()


if __name__ == "__main__":
    print(f"[billing-worker] tick={TICK_SEC}s R_BUYOUT={R_BUYOUT}")
    while True:
        try:
            tick()
        except Exception as e:
            print("[billing-worker] tick error:", e)
        time.sleep(TICK_SEC)
