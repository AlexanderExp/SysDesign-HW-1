# services/rental-core/app/main.py
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from .db import SessionLocal
from .models import Rental, IdempotencyKey
from . import clients
from .config_cache import start_configs_refresher, load_initial_or_die
import json

app = FastAPI()


@app.on_event("startup")
def _startup():
    if not load_initial_or_die():
        raise RuntimeError("failed to load initial configs")
    start_configs_refresher(app)


class QuoteIn(BaseModel):
    station_id: str
    user_id: str


@app.post("/rentals/quote")
def quote(body: QuoteIn):
    # твоя текущая реализация (как была)
    sd = clients.get_station_data(body.station_id)
    tariff = clients.get_tariff(sd.tariff_id)
    user = clients.get_user_profile(body.user_id)
    price_per_hour = tariff.price_per_hour
    free_min = tariff.free_period_min
    deposit = tariff.default_deposit if not user.trusted else max(
        0, tariff.default_deposit // 2)
    return {
        "quote_id": clients.uuid4(),
        "user_id": body.user_id,
        "station_id": body.station_id,
        "price_per_hour": price_per_hour,
        "free_period_min": free_min,
        "deposit": deposit,
        "expires_in_sec": 60
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

        # соберем все входные из внешних сервисов (как у тебя было в quote)
        # тут для простоты считаем, что фронт прислал все нужное ранее (можно связать с твоей логикой quote)
        # выгружаем powerbank
        # возьми из сохраненного контекста quote, если он у тебя хранится
        station_id = "some-station-id"
        user_id = "u1"                  # —//—
        sd = clients.get_station_data(station_id)
        tariff = clients.get_tariff(sd.tariff_id)
        user = clients.get_user_profile(user_id)
        deposit = tariff.default_deposit if not user.trusted else max(
            0, tariff.default_deposit // 2)

        ej = clients.eject_powerbank(station_id)
        if not ej.success:
            raise HTTPException(409, "no free slots / eject failed")

        now = datetime.now(timezone.utc)
        r = Rental(
            id=clients.uuid4(),
            user_id=user_id,
            powerbank_id=ej.powerbank_id,
            price_per_hour=tariff.price_per_hour,
            free_period_min=tariff.free_period_min,
            deposit=deposit,
            status="ACTIVE",
            total_amount=0,
            started_at=now,
        )
        s.add(r)
        s.flush()

        # >>> NEW: держим депозит
        try:
            clients.hold_money_for_order(
                user_id=r.user_id, order_id=r.id, amount=r.deposit)
        except Exception as e:
            s.rollback()
            raise HTTPException(502, f"hold failed: {e}")

        resp = {
            "order_id": r.id,
            "status": r.status,
            "powerbank_id": r.powerbank_id,
            "total_amount": r.total_amount,
            "debt": 0
        }
        s.add(IdempotencyKey(key=Idempotency_Key, scope="start", user_id=r.user_id,
                             response_json=clients.json_dumps(resp)))
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

        # меняем статус и время завершения
        r.status = "FINISHED"
        r.finished_at = datetime.now(timezone.utc)
        s.flush()

        # >>> NEW: финальный clear (зачисление суммы и возврат остатка депозита — логика на стороне external-stubs)
        try:
            clients.clear_money_for_order(
                user_id=r.user_id, order_id=r.id, amount=r.total_amount)
        except Exception as e:
            # не валим запрос: заказ уже завершили; долг (если нужен) фиксируется воркером
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
