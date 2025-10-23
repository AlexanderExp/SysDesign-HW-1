# services/rental-core/app/main.py
from datetime import timedelta  # ниже используется
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import text
from .db import SessionLocal
from .models import Rental, IdempotencyKey
from . import clients
from .config_cache import start_configs_refresher, load_initial_or_die
import json

app = FastAPI()


def _load_quote_or_none(s, quote_id: str) -> Optional[dict]:
    """Совместимость с тестами: просто обёртка над _get_quote."""
    return _get_quote(s, quote_id)


def _consume_quote(s, quote_id: str) -> None:
    """
    Идемпотентно «потребляет» (удаляет) квоту.
    Тестам достаточно факта пропажи; повторные вызовы — ок.
    """
    _ensure_quotes_schema(s)
    s.execute(text("DELETE FROM quotes WHERE id = :id"), {"id": quote_id})

@app.on_event("startup")
def _startup():
    if not load_initial_or_die():
        raise RuntimeError("failed to load initial configs")
    start_configs_refresher(app)

# --------- ВСПОМОГАТЕЛЬНЫЕ SQL-ХЕЛПЕРЫ (portable для SQLite/Postgres) ---------


def _ensure_quotes_schema(s) -> None:
    # без TIMESTAMPTZ/DEFAULT now(), чтобы было совместимо с SQLite
    s.execute(text("""
        CREATE TABLE IF NOT EXISTS quotes (
            id           VARCHAR(64)  PRIMARY KEY,
            user_id      VARCHAR(64)  NOT NULL,
            station_id   VARCHAR(128) NOT NULL,
            price_per_hour   INTEGER  NOT NULL,
            free_period_min  INTEGER  NOT NULL,
            deposit          INTEGER  NOT NULL,
            expires_at   DATETIME     NOT NULL,
            created_at   DATETIME     NOT NULL
        )
    """))


def _ensure_debts_schema(s) -> None:
    s.execute(text("""
        CREATE TABLE IF NOT EXISTS debts (
            rental_id       VARCHAR(64) PRIMARY KEY,
            amount_total    INTEGER     NOT NULL DEFAULT 0,
            updated_at      DATETIME    NOT NULL,
            attempts        INTEGER     NOT NULL DEFAULT 0,
            last_attempt_at DATETIME    NULL
        )
    """))


def _insert_quote(
    s,
    quote_id: str,
    user_id: str,
    station_id: str,
    price_per_hour: int,
    free_period_min: int,
    deposit: int,
    expires_at: datetime,
    created_at: Optional[datetime] = None,
) -> None:
    _ensure_quotes_schema(s)
    if created_at is None:
        created_at = datetime.now(timezone.utc)

    s.execute(
        text("""
            INSERT INTO quotes (
                id, user_id, station_id, price_per_hour, free_period_min, deposit, expires_at, created_at
            ) VALUES (
                :id, :user_id, :station_id, :pph, :free_min, :deposit, :expires_at, :created_at
            )
        """),
        {
            "id": quote_id,
            "user_id": user_id,
            "station_id": station_id,
            "pph": price_per_hour,
            "free_min": free_period_min,
            "deposit": deposit,
            "expires_at": expires_at,
            "created_at": created_at,
        },
    )
    s.flush()


def _get_quote(s, quote_id: str) -> Optional[dict]:
    _ensure_quotes_schema(s)
    row = s.execute(
        text("""
            SELECT id, user_id, station_id, price_per_hour, free_period_min, deposit, expires_at, created_at
            FROM quotes WHERE id = :id
        """),
        {"id": quote_id},
    ).mappings().one_or_none()
    return dict(row) if row else None


def _attach_deposit_debt(s, rental_id: str, amount: int, now: datetime) -> None:
    """
    Навешиваем долг на заказ (используется при деградации start, когда payments недоступны).
    Если запись существует — увеличиваем долг; иначе создаём.
    """
    _ensure_debts_schema(s)
    existing = s.execute(
        text("SELECT amount_total FROM debts WHERE rental_id = :rid"),
        {"rid": rental_id},
    ).fetchone()

    if existing:
        s.execute(
            text("""
                UPDATE debts
                SET amount_total = amount_total + :delta,
                    updated_at = :ts
                WHERE rental_id = :rid
            """),
            {"delta": amount, "ts": now, "rid": rental_id},
        )
    else:
        s.execute(
            text("""
                INSERT INTO debts (rental_id, amount_total, updated_at, attempts, last_attempt_at)
                VALUES (:rid, :amt, :ts, 0, NULL)
            """),
            {"rid": rental_id, "amt": amount, "ts": now},
        )
    s.flush()

# --------- API-модели ---------


class QuoteIn(BaseModel):
    station_id: str
    user_id: str


@app.post("/rentals/quote")
def quote(body: QuoteIn):
    sd = clients.get_station_data(body.station_id)
    tariff = clients.get_tariff(sd.tariff_id)
    user = clients.get_user_profile(body.user_id)
    price_per_hour = tariff.price_per_hour
    free_min = tariff.free_period_min
    deposit = tariff.default_deposit if not user.trusted else max(
        0, tariff.default_deposit // 2)

    # храним оффер локально (БД) — чтобы старт мог его проверить
    now = datetime.now(timezone.utc)
    qid = clients.uuid4()
    with SessionLocal() as s:
        _insert_quote(
            s, qid, body.user_id, body.station_id,
            price_per_hour, free_min, deposit,
            expires_at=now.replace(microsecond=0) + timedelta(seconds=60),
            created_at=now
        )
        s.commit()

    return {
        "quote_id": qid,
        "user_id": body.user_id,
        "station_id": body.station_id,
        "price_per_hour": price_per_hour,
        "free_period_min": free_min,
        "deposit": deposit,
        "expires_in_sec": 60,
    }


class StartIn(BaseModel):
    quote_id: str


@app.post("/rentals/start")
def start_rental(body: StartIn, Idempotency_Key: Optional[str] = Header(default=None)):
    if not Idempotency_Key:
        raise HTTPException(400, "missing Idempotency-Key")

    with SessionLocal() as s:
        # идемпотентность
        ik = s.get(IdempotencyKey, Idempotency_Key)
        if ik:
            return json.loads(ik.response_json)

        # валидируем и берём параметры из сохранённого quote
        q = _get_quote(s, body.quote_id)
        if not q:
            raise HTTPException(400, "invalid or expired quote")

        if datetime.now(timezone.utc) > q["expires_at"]:
            raise HTTPException(400, "quote expired")

        # пытаемся выдать павербанк
        ej = clients.eject_powerbank(q["station_id"])
        if not ej.success:
            raise HTTPException(409, "no free slots / eject failed")

        now = datetime.now(timezone.utc)
        r = Rental(
            id=clients.uuid4(),
            user_id=q["user_id"],
            powerbank_id=ej.powerbank_id,
            price_per_hour=q["price_per_hour"],
            free_period_min=q["free_period_min"],
            deposit=q["deposit"],
            status="ACTIVE",
            total_amount=0,
            started_at=now,
        )
        s.add(r)
        s.flush()

        # держим депозит — НО допускаем деградацию (навешиваем долг и всё равно запускаем)
        try:
            clients.hold_money_for_order(
                user_id=r.user_id, order_id=r.id, amount=r.deposit)
        except Exception:
            # payments недоступны -> навешиваем начальный долг = deposit, воркер позже попробует списать
            _attach_deposit_debt(s, r.id, r.deposit, now)

        resp = {
            "order_id": r.id,
            "status": r.status,
            "powerbank_id": r.powerbank_id,
            "total_amount": r.total_amount,
            "debt": 0
        }
        s.add(IdempotencyKey(key=Idempotency_Key, scope="start", user_id=r.user_id,
                             response_json=json.dumps(resp, ensure_ascii=False)))
        s.commit()
        return resp


class StopIn(BaseModel):
    station_id: str


@app.post("/rentals/{order_id}/stop")
def stop_rental(order_id: str, body: StopIn):
    with SessionLocal() as s:
        r = s.get(Rental, order_id)
        if not r:
            raise HTTPException(404, "order not found")

        # идемпотентность: если уже завершен — просто отдаем текущее состояние
        if r.status == "FINISHED":
            return {
                "order_id": r.id,
                "status": r.status,
                "powerbank_id": r.powerbank_id,
                "total_amount": r.total_amount,
                "debt": 0
            }

        r.status = "FINISHED"
        r.finished_at = datetime.now(timezone.utc)
        s.flush()

        try:
            clients.clear_money_for_order(
                user_id=r.user_id, order_id=r.id, amount=r.total_amount)
        except Exception:
            # долг (если есть) доберёт биллинг-воркер, не валим стоп
            pass

        s.commit()
        return {
            "order_id": r.id,
            "status": r.status,
            "powerbank_id": r.powerbank_id,
            "total_amount": r.total_amount,
            "debt": 0
        }


@app.get("/rentals/{order_id}/status")
def status(order_id: str):
    with SessionLocal() as s:
        r = s.get(Rental, order_id)
        if not r:
            raise HTTPException(404, "order not found")
        return {
            "order_id": r.id,
            "status": r.status,
            "powerbank_id": r.powerbank_id,
            "total_amount": r.total_amount,
            "debt": 0
        }


@app.get("/health")
def health():
    return {"ok": True}
