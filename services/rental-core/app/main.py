from .db import SessionLocal
from .schemas import StopRequest, OrderStatus
from datetime import datetime, timezone
import time
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Header
from . import clients
from .schemas import QuoteRequest, QuoteResponse, StartRequest, OrderStatus, StopRequest
from .db import SessionLocal, init_db
from .models import Rental
from . import offer_store
from .config import CONFIG_REFRESH_SEC
import asyncio
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
import json
from .models import IdempotencyKey, PaymentAttempt, Debt



app = FastAPI(title="rental-core")

# _offers: dict[str, dict] = {}


@app.on_event("startup")
def init_configs():
    # конфиг обязателен на старте
    clients.refresh_configs()
    init_db()
    # фон: обновление конфигов
    loop = asyncio.get_event_loop()
    app.state._cfg_task = loop.create_task(_config_refresher())


@app.on_event("shutdown")
def stop_bg():
    t = getattr(app.state, "_cfg_task", None)
    if t:
        t.cancel()


async def _config_refresher():
    while True:
        try:
            await asyncio.sleep(CONFIG_REFRESH_SEC)
            clients.refresh_configs()
        except Exception:
            # по ТЗ можно бесконечно пользоваться старыми конфигами
            pass



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
    # _offers[qid] = {
    #     "user_id": req.user_id,
    #     "station_id": req.station_id,
    #     "price_per_hour": price,
    #     "free_period_min": free_min,
    #     "deposit": deposit,
    #     "expires_at": expires,
    #     "tariff_version": tariff.id,
    # }

    offer_store.save(qid, {
        "user_id": req.user_id,
        "station_id": req.station_id,
        "price_per_hour": price,
        "free_period_min": free_min,
        "deposit": deposit,
        "tariff_version": tariff.id,
    })

    return QuoteResponse(
        quote_id=qid, user_id=req.user_id, station_id=req.station_id,
        price_per_hour=price, free_period_min=free_min, deposit=deposit, expires_in_sec=60
    )


@app.post("/rentals/start", response_model=OrderStatus)
def start_rental(req: StartRequest, idempotency_key: str | None = Header(None)):
    # 1) Идемпотентность: если есть сохранённый ответ — возвращаем его
    if idempotency_key:
        with SessionLocal() as s:
            rec = s.get(IdempotencyKey, idempotency_key)
            if rec and rec.scope == "start_rental":
                return json.loads(rec.response_json)

    # 2) Забираем оффер из Redis (одноразовый, с TTL). Нет — просрочен/уже использован
    offer = offer_store.pop(req.quote_id)
    if not offer:
        raise HTTPException(status_code=409, detail="offer missing or expired")

    order_id = str(uuid.uuid4())

    # 3) Платёж: пробуем удержать депозит, но не блокируем старт при ошибке (будет долг/ретраи в воркере)
    try:
        if offer["deposit"] > 0:
            clients.hold_money_for_order(
                offer["user_id"], order_id, offer["deposit"])
    except Exception:
        pass  # логика долга будет в billing-worker

    # 4) Выдача павербанка
    ej = clients.eject_powerbank(offer["station_id"])
    if not ej.success or not ej.powerbank_id:
        # откат холда (best-effort)
        try:
            clients.clear_money_for_order(offer["user_id"], order_id, 0)
        except Exception:
            pass
        raise HTTPException(status_code=409, detail="no powerbank available")

    # 5) Сохраняем заказ в БД
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

    resp = OrderStatus(
        order_id=order_id, status="active", powerbank_id=ej.powerbank_id, total_amount=0
    )

    # 6) Сохраняем идемпотентный ответ (если был ключ)
    if idempotency_key:
        try:
            with SessionLocal() as s:
                s.add(
                    IdempotencyKey(
                        key=idempotency_key,
                        scope="start_rental",
                        user_id=offer["user_id"],
                        response_json=json.dumps(resp.model_dump()),
                    )
                )
                s.commit()
        except IntegrityError:
            # Гонка: ключ уже записан другим запросом — читаем и возвращаем
            with SessionLocal() as s2:
                rec = s2.get(IdempotencyKey, idempotency_key)
                if rec:
                    return json.loads(rec.response_json)

    return resp


@app.get("/rentals/{rental_id}/status", response_model=OrderStatus)
def get_status(rental_id: str):
    with SessionLocal() as s:
        r = s.get(Rental, rental_id)
        if not r:
            raise HTTPException(status_code=404, detail="not found")

        paid = s.query(func.coalesce(func.sum(PaymentAttempt.amount), 0))\
            .filter(PaymentAttempt.rental_id == rental_id,
                    PaymentAttempt.success.is_(True))\
            .scalar()

        debt = s.query(Debt).filter(Debt.rental_id == rental_id).one_or_none()
        debt_amount = debt.amount_total if debt else 0

    return {
        "order_id": r.id,
        "status": r.status,
        "powerbank_id": r.powerbank_id,
        "total_amount": int(paid),   # совместимость со старым полем
        "debt": int(debt_amount)     # новое поле (удобно для отчётов)
    }


@app.post("/rentals/{order_id}/stop", response_model=OrderStatus)
def stop_rental(order_id: str, req: StopRequest):
    with SessionLocal() as s:
        r = s.get(Rental, order_id)
        if not r:
            raise HTTPException(404, "order not found")

        # считаем итог на лету (как в /status), без побочных эффектов пока
        now = datetime.now(timezone.utc)
        elapsed_sec = max(0, (now - r.started_at).total_seconds())
        if elapsed_sec <= r.free_period_min * 60:
            total = 0
        else:
            hours = int(elapsed_sec // 3600)
            total = hours * r.price_per_hour

        # ИДЕМПОТЕНТНОСТЬ: если уже завершён/выкуплен — вернуть текущий снимок
        if r.status != "active":
            return OrderStatus(
                order_id=r.id,
                status=r.status,
                powerbank_id=r.powerbank_id,
                # если total_amount ещё не записан, вернём вычисленное значение
                total_amount=r.total_amount if r.total_amount is not None else total,
            )

        # Первое завершение — фиксируем
        r.total_amount = total
        r.status = "finished"
        r.finished_at = now
        s.add(r)
        s.commit()

    # Вне транзакции — best-effort списание
    try:
        clients.clear_money_for_order(r.user_id, r.id, r.total_amount)
    except Exception:
        pass

    return OrderStatus(
        order_id=r.id,
        status=r.status,
        powerbank_id=r.powerbank_id,
        total_amount=r.total_amount,
    )
