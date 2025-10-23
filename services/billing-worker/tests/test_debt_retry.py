# services/billing-worker/tests/test_debt_retry.py
import types
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os
import sys

# позволяем "import main" из папки billing-worker
sys.path.append(os.path.abspath("services/billing-worker"))

import main as bw  # noqa: E402


def setup_sqlite(monkeypatch):
    eng = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Session = sessionmaker(bind=eng, autoflush=False,
                           autocommit=False, expire_on_commit=False, future=True)
    bw.engine = eng
    bw.SessionLocal = Session
    bw.Base.metadata.create_all(eng)
    bw.ensure_schema()
    return eng, Session


def test_due_amount_flooring():
    now = datetime.now(timezone.utc)
    start = now - timedelta(seconds=90)  # 1.5 минуты
    # 60р/ч => за 90с должно выйти 1р
    assert bw._due_amount(60, 0, start, now) == 1


def test_backoff_capped():
    bw.DEBT_RETRY_BASE_SEC = 60
    bw.DEBT_RETRY_MAX_SEC = 600
    assert bw._backoff_seconds(0) == 60
    assert bw._backoff_seconds(1) == 120
    assert bw._backoff_seconds(4) == 600  # кап


def test_historical_debt_success(monkeypatch):
    _, Session = setup_sqlite(monkeypatch)

    now = datetime.now(timezone.utc)
    with Session() as s:
        r = bw.Rental(
            id="r1", user_id="u1", powerbank_id="pb", price_per_hour=60,
            free_period_min=0, deposit=100, status="ACTIVE", total_amount=0,
            started_at=now - timedelta(hours=1)
        )
        s.add(r)
        d = bw.Debt(rental_id="r1", amount_total=250, updated_at=now - timedelta(hours=1), attempts=2,
                    last_attempt_at=now - timedelta(hours=2))
        s.add(d)
        s.commit()

    monkeypatch.setattr(bw, "_try_charge", lambda user_id,
                        rid, amt: (True, None))
    bw.DEBT_CHARGE_STEP = 100

    with Session() as s:
        r = s.get(bw.Rental, "r1")
        charged, debt_delta = bw._maybe_collect_historical_debt(s, r, now)
        s.commit()

    assert charged == 100
    assert debt_delta == -100

    with Session() as s:
        d = s.get(bw.Debt, "r1")
        assert d.amount_total == 150
        assert d.attempts == 0
        assert d.last_attempt_at is not None
        r = s.get(bw.Rental, "r1")
        assert r.total_amount == 100


def test_historical_debt_failure(monkeypatch):
    _, Session = setup_sqlite(monkeypatch)

    now = datetime.now(timezone.utc)
    with Session() as s:
        r = bw.Rental(
            id="r2", user_id="u2", powerbank_id="pb", price_per_hour=60,
            free_period_min=0, deposit=100, status="ACTIVE", total_amount=0,
            started_at=now - timedelta(hours=1)
        )
        s.add(r)
        d = bw.Debt(rental_id="r2", amount_total=70, updated_at=now - timedelta(hours=1), attempts=0,
                    last_attempt_at=now - timedelta(hours=2))
        s.add(d)
        s.commit()

    monkeypatch.setattr(bw, "_try_charge", lambda user_id,
                        rid, amt: (False, "fail"))
    bw.DEBT_CHARGE_STEP = 100  # меньше долга возьмётся 70

    with Session() as s:
        r = s.get(bw.Rental, "r2")
        charged, debt_delta = bw._maybe_collect_historical_debt(s, r, now)
        s.commit()

    assert charged == 0
    assert debt_delta == 0

    with Session() as s:
        d = s.get(bw.Debt, "r2")
        assert d.amount_total == 70
        assert d.attempts == 1
        assert d.last_attempt_at is not None
        r = s.get(bw.Rental, "r2")
        assert r.total_amount == 0
