from typing import Optional
import requests
from cachetools import TTLCache, cached
from .config import EXTERNAL_BASE, TARIFF_TTL_SEC, HTTP_TIMEOUT_SEC
from model import Tariff, UserProfile, Slot, StationData, ConfigMap, EjectResponse

session = requests.Session()
session.headers.update({"User-Agent": "rental-core/1.0"})


def _get(path: str, params: Optional[dict] = None):
    r = session.get(EXTERNAL_BASE + path, params=params,
                    timeout=HTTP_TIMEOUT_SEC)
    r.raise_for_status()
    return r.json()


def _post(path: str, payload: dict):
    r = session.post(EXTERNAL_BASE + path, json=payload,
                     timeout=HTTP_TIMEOUT_SEC)
    r.raise_for_status()
    return r.json()


def get_station_data(station_id: str) -> StationData:
    j = _get("/station-data", {"id": station_id})
    slots = [Slot(index=s["index"], empty=s["empty"], charge=s["charge"])
             for s in j["slots"]]
    return StationData(id=station_id, tariff_id=j["tariff_id"], location=j["location"], slots=slots)


# --- tariffs: LRU+TTL (готовая реализация через cachetools) ---
_tariff_cache = TTLCache(maxsize=1024, ttl=TARIFF_TTL_SEC)


@cached(cache=_tariff_cache)
def get_tariff(zone_id: str) -> Tariff:
    j = _get("/tariff", {"id": zone_id})
    return Tariff(id=zone_id,
                  price_per_hour=int(j["price_per_hour"]),
                  free_period_min=int(j["free_period_min"]),
                  default_deposit=int(j["default_deposit"]))

# --- users: с фоллбэком на «жадный прайсинг» ---


def get_user_profile(user_id: str) -> UserProfile:
    try:
        j = _get("/user-profile", {"id": user_id})
        return UserProfile(id=user_id,
                           has_subscribtion=bool(j["has_subscribtion"]),
                           trusted=bool(j["trusted"]))
    except Exception:
        # fallback: без подписки и недоверенный (жадно)
        return UserProfile(id=user_id, has_subscribtion=False, trusted=False)


# --- configs: получаем на старте, далее обновляем фоном в main.py ---
_config: Optional[ConfigMap] = None


def set_config(c: ConfigMap):  # вызовем из фонового рефрешера
    global _config
    _config = c


def get_configs() -> ConfigMap:
    global _config
    if _config is None:
        j = _get("/configs")
        _config = ConfigMap(j)
    return _config


def refresh_configs() -> ConfigMap:
    j = _get("/configs")
    c = ConfigMap(j)
    set_config(c)
    return c

# --- payments / eject ---


def eject_powerbank(station_id: str) -> EjectResponse:
    j = _get("/eject-powerbank", {"station_id": station_id})
    return EjectResponse(success=j["success"], powerbank_id=j["powerbank_id"])


def hold_money_for_order(user_id: str, order_id: str, amount: int):
    _post("/hold-money-for-order",
          {"user_id": user_id, "order_id": order_id, "amount": amount})


def clear_money_for_order(user_id: str, order_id: str, amount: int):
    _post("/clear-money-for-order",
          {"user_id": user_id, "order_id": order_id, "amount": amount})
