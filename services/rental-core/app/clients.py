# services/rental-core/app/clients.py
from __future__ import annotations
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from threading import RLock
from cachetools import TTLCache, cached

from .config import EXTERNAL_BASE, TARIFF_TTL_SEC, HTTP_TIMEOUT_SEC
from .model import Tariff, UserProfile, Slot, StationData, ConfigMap, EjectResponse


# ---------- HTTP session с ретраями и таймаутами ----------
def _build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3, connect=3, read=3,
        backoff_factor=0.3,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": "rental-core/1.0"})
    return s


_session = _build_session()


def _url(path: str) -> str:
    return f"{EXTERNAL_BASE.rstrip('/')}/{path.lstrip('/')}"


def _get(path: str, params: Optional[dict] = None) -> dict:
    r = _session.get(_url(path), params=params, timeout=HTTP_TIMEOUT_SEC)
    r.raise_for_status()
    return r.json()


def _post(path: str, payload: dict) -> dict:
    r = _session.post(_url(path), json=payload, timeout=HTTP_TIMEOUT_SEC)
    r.raise_for_status()
    # /hold-money-for-order и /clear-money-for-order возвращают json
    return r.json() if r.content else {}


# ---------- stations ----------
def get_station_data(station_id: str) -> StationData:
    j = _get("/station-data", {"id": station_id})
    slots = [Slot(index=s["index"], empty=s["empty"], charge=s["charge"])
             for s in j["slots"]]
    return StationData(
        id=station_id,
        tariff_id=j["tariff_id"],
        location=j["location"],
        slots=slots
    )


# ---------- tariffs: LRU+TTL ----------
# Важно: TTLCache не вернёт протухшие данные — если TTL истёк, будет реальный вызов.
# Если апстрим недоступен, получим исключение -> это соответствует требованию «старше TTL — ошибка».
_tariff_cache = TTLCache(maxsize=1024, ttl=TARIFF_TTL_SEC)


@cached(cache=_tariff_cache)
def get_tariff(zone_id: str) -> Tariff:
    j = _get("/tariff", {"id": zone_id})
    return Tariff(
        id=zone_id,
        price_per_hour=int(j["price_per_hour"]),
        free_period_min=int(j["free_period_min"]),
        default_deposit=int(j["default_deposit"]),
    )


# ---------- users: с фоллбэком на «жадный» профиль ----------
def get_user_profile(user_id: str) -> UserProfile:
    try:
        j = _get("/user-profile", {"id": user_id})
        return UserProfile(
            id=user_id,
            has_subscribtion=bool(j["has_subscribtion"]),
            trusted=bool(j["trusted"]),
        )
    except Exception:
        # Фоллбэк: пользователь без подписки и не trusted.
        # Жадный прайсинг применяем в бизнес-логике (цена/депозит из конфигов).
        return UserProfile(id=user_id, has_subscribtion=False, trusted=False)


# ---------- configs: кэш + потокобезопасный refresh ----------
_config_lock = RLock()
_config_obj: Optional[ConfigMap] = None


def set_config(c: ConfigMap) -> None:
    global _config_obj
    with _config_lock:
        _config_obj = c


def get_configs() -> ConfigMap:
    global _config_obj
    with _config_lock:
        if _config_obj is None:
            j = _get("/configs")
            _config_obj = ConfigMap(j)
        return _config_obj


def refresh_configs() -> ConfigMap:
    j = _get("/configs")
    c = ConfigMap(j)
    set_config(c)
    return c


# ---------- payments / eject ----------
def eject_powerbank(station_id: str) -> EjectResponse:
    j = _get("/eject-powerbank", {"station_id": station_id})
    return EjectResponse(success=j["success"], powerbank_id=j["powerbank_id"])


def hold_money_for_order(user_id: str, order_id: str, amount: int) -> None:
    _post("/hold-money-for-order",
          {"user_id": user_id, "order_id": order_id, "amount": amount})


def clear_money_for_order(user_id: str, order_id: str, amount: int) -> None:
    _post("/clear-money-for-order",
          {"user_id": user_id, "order_id": order_id, "amount": amount})
