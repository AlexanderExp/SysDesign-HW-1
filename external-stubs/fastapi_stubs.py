from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from model import EjectResponse, Slot, StationData, Tariff, UserProfile
from pydantic import BaseModel

app = FastAPI()


@app.get("/station-data")
async def get_station_data(
    id: Optional[str] = Query(None, description="An optional ID parameter"),
):
    if id is None:
        raise HTTPException(
            status_code=400, detail="ID parameter is required and cannot be empty."
        )

    slots = [] if id == "empty-station-id" else [Slot(1, True, 0), Slot(2, False, 100)]
    return StationData(
        id, tariff_id="tariff18", location="Королев, универмаг Детский мир", slots=slots
    )


@app.get("/tariff")
async def get_tariff(
    id: Optional[str] = Query(None, description="An optional ID parameter"),
):
    if id is None:
        raise HTTPException(
            status_code=400, detail="ID parameter is required and cannot be empty."
        )

    # return Tariff(id, price_per_hour=50, free_period_min=5, default_deposit=300)
    return Tariff(id, price_per_hour=60, free_period_min=0, default_deposit=300)


@app.get("/user-profile")
async def get_user_profile(
    id: Optional[str] = Query(None, description="An optional ID parameter"),
):
    if id is None:
        raise HTTPException(
            status_code=400, detail="ID parameter is required and cannot be empty."
        )

    return UserProfile(id, has_subscribtion=False, trusted=False)


@app.get("/configs")
async def get_configs():
    return {"price_coeff_settings": {"last_banks_increase": 1.5}}


@app.get("/eject-powerbank")
async def eject_powerbank(
    station_id: Optional[str] = Query(None, description="An optional ID parameter"),
):
    if station_id is None:
        raise HTTPException(
            status_code=400,
            detail="Station ID parameter is required and cannot be empty.",
        )

    if station_id == "empty-station-id":
        return EjectResponse(success=False, powerbank_id="")
    else:
        return EjectResponse(success=True, powerbank_id="powerbank_638")


class MoneyRequest(BaseModel):
    user_id: str
    order_id: str
    amount: int


@app.post("/hold-money-for-order")
async def hold_money_for_order(request: MoneyRequest):
    if request.user_id is None:
        raise HTTPException(
            status_code=400, detail="user_id parameter is required and cannot be empty."
        )
    return {"status": "success"}


@app.post("/clear-money-for-order")
async def clear_money_for_order(request: MoneyRequest):
    if request.user_id is None:
        raise HTTPException(
            status_code=400, detail="user_id parameter is required and cannot be empty."
        )
    return {"status": "success"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3629, log_level="info")
