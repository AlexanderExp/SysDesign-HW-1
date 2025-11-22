import os
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# позволяем импортировать app.main
sys.path.append(os.path.abspath("services/rental-core"))

from app import main as rc  # noqa: E402


def setup_sqlite(monkeypatch):
    eng = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Session = sessionmaker(
        bind=eng, autoflush=False, autocommit=False, expire_on_commit=False, future=True
    )
    # подменяем SessionLocal
    rc.SessionLocal = Session
    return eng, Session


def test_quotes_lifecycle(monkeypatch):
    _, Session = setup_sqlite(monkeypatch)
    now = datetime.now(timezone.utc)

    with Session() as s:
        # вставили quote
        qid = "q1"
        rc._insert_quote(s, qid, "u1", "st1", 60, 0, 300, now)
        s.commit()

    with Session() as s:
        q = rc._load_quote_or_none(s, "q1")
        assert q is not None
        assert q["user_id"] == "u1"
        assert q["station_id"] == "st1"

    with Session() as s:
        rc._consume_quote(s, "q1")
        s.commit()

    with Session() as s:
        q = rc._load_quote_or_none(s, "q1")
        assert q is None


def test_attach_deposit_debt(monkeypatch):
    eng, Session = setup_sqlite(monkeypatch)
    now = datetime.now(timezone.utc)

    with Session() as s:
        rc._attach_deposit_debt(s, "r1", 200, now)
        s.commit()

    with eng.begin() as conn:
        row = conn.execute(
            text("SELECT rental_id, amount_total FROM debts WHERE rental_id='r1'")
        ).first()
        assert row is not None
        assert row.amount_total == 200

    # повторное навешивание — увеличивает сумму
    with Session() as s:
        rc._attach_deposit_debt(s, "r1", 50, now)
        s.commit()

    with eng.begin() as conn:
        row = conn.execute(
            text("SELECT rental_id, amount_total FROM debts WHERE rental_id='r1'")
        ).first()
        assert row.amount_total == 250
