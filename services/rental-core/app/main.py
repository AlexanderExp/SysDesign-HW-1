import time
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException
from . import clients
from .schemas import QuoteRequest, QuoteResponse, StartRequest, OrderStatus
from .db import SessionLocal, init_db
from .models import Rental

app = FastAPI(title="rental-core")

_offers: dict[str, dict] = {}


@app.on_event("startup")
def init_configs():
    # конфиги обязательны на старте
    clients.refresh_configs()
    # создаём таблицы (позже заменим на alembic миграции)
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/rentals/quote", response_model=QuoteResponse)
def create_quote(req: QuoteRequest):
    station = clients.get_station_data(req.station_id)
    if station is None:
        raise HTTPException(503, "stations unavailable")

    tariff = clients.get_tariff(station.tariff_id)
    user = clients.get_user_profile(req.user_id)
    cfg = clients.get_configs()

    price = tariff.price_per_hour
    if getattr(cfg, "price_coeff_settings", None):
        available = sum(0 if s.empty else 1 for s in station.slots)
        if available <= 2:
            inc = float(cfg.price_coeff_settings["last_banks_increase"])
            price = int(price * inc)

    free_min = tariff.free_period_min
    if user.has_subscribtion:
        free_min = max(free_min, 30)

    deposit = 0 if user.trusted else tariff.default_deposit

    qid = str(uuid.uuid4())
    expires = datetime.utcnow() + timedelta(seconds=60)
    _offers[qid] = {
        "user_id": req.user_id,
        "station_id": req.station_id,
        "price_per_hour": price,
        "free_period_min": free_min,
        "deposit": deposit,
        "expires_at": expires,
        "tariff_version": tariff.id,
    }
    return QuoteResponse(
        quote_id=qid, user_id=req.user_id, station_id=req.station_id,
        price_per_hour=price, free_period_min=free_min, deposit=deposit, expires_in_sec=60
    )


@app.post("/rentals/start", response_model=OrderStatus)
def start_rental(req: StartRequest):
    offer = _offers.get(req.quote_id)
    if not offer:
        raise HTTPException(409, "offer missing or already used")
    if offer["expires_at"] < datetime.utcnow():
        _offers.pop(req.quote_id, None)
        raise HTTPException(409, "offer expired")

    order_id = str(uuid.uuid4())

    # попытка холда депозита (если платежи недоступны — не блокируем старт)
    try:
        if offer["deposit"] > 0:
            clients.hold_money_for_order(
                offer["user_id"], order_id, offer["deposit"])
    except Exception:
        pass

    ej = clients.eject_powerbank(offer["station_id"])
    if not ej.success or not ej.powerbank_id:
        try:
            clients.clear_money_for_order(offer["user_id"], order_id, 0)
        except Exception:
            pass
        raise HTTPException(409, "no powerbank available")

    _offers.pop(req.quote_id, None)

    # сохраняем заказ в БД
    with SessionLocal() as s:
        r = Rental(
            id=order_id,
            user_id=offer["user_id"],
            powerbank_id=ej.powerbank_id,
            price_per_hour=offer["price_per_hour"],
            free_period_min=offer["free_period_min"],
            deposit=offer["deposit"],
            status="active",
            total_amount=0,
        )
        s.add(r)
        s.commit()

    return OrderStatus(order_id=order_id, status="active",
                       powerbank_id=ej.powerbank_id, total_amount=0)


@app.get("/rentals/{order_id}/status", response_model=OrderStatus)
def get_status(order_id: str):
    with SessionLocal() as s:
        r = s.get(Rental, order_id)
        if not r:
            raise HTTPException(404, "order not found")

        # расчёт накопленной стоимости (упрощённый, как в шаблоне)
        started_ts = r.started_at
        now = datetime.now(timezone.utc)
        elapsed_sec = max(0, (now - started_ts).total_seconds())
        if elapsed_sec <= r.free_period_min * 60:
            total = 0
        else:
            hours = int(elapsed_sec // 3600)
            total = hours * r.price_per_hour

        # обновим кешированное поле total_amount (необязательно)
        if total != r.total_amount and r.status == "active":
            r.total_amount = total
            s.add(r)
            s.commit()

        return OrderStatus(
            order_id=r.id,
            status=r.status,
            powerbank_id=r.powerbank_id,
            total_amount=r.total_amount,
        )
