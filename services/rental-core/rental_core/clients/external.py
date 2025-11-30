from typing import Optional, Tuple

import requests
from cachetools import TTLCache, cached
from loguru import logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from rental_core.config.settings import Settings
from rental_core.core.circuit_breaker import CircuitBreakerConfig


class StationData:
    def __init__(self, id: str, tariff_id: str, location: str, slots: list):
        self.id = id
        self.tariff_id = tariff_id
        self.location = location
        self.slots = slots


class Slot:
    def __init__(self, index: int, empty: bool, charge: int):
        self.index = index
        self.empty = empty
        self.charge = charge


class Tariff:
    def __init__(
        self, id: str, price_per_hour: int, free_period_min: int, default_deposit: int
    ):
        self.id = id
        self.price_per_hour = price_per_hour
        self.free_period_min = free_period_min
        self.default_deposit = default_deposit


class UserProfile:
    def __init__(self, id: str, has_subscribtion: bool, trusted: bool):
        self.id = id
        self.has_subscribtion = has_subscribtion
        self.trusted = trusted


class EjectResponse:
    def __init__(self, success: bool, powerbank_id: str):
        self.success = success
        self.powerbank_id = powerbank_id


class ConfigMap:
    def __init__(self, data: dict):
        self.data = data

    def get(self, key: str, default=None):
        return self.data.get(key, default)


class ExternalClient:
    def __init__(self, settings: Settings):
        self._session = self._build_session()
        self._timeout = settings.http_timeout_sec
        self._external_base = settings.external_base
        self._tariff_cache = TTLCache(maxsize=1024, ttl=settings.tariff_ttl_sec)

        self._cb_config = CircuitBreakerConfig(settings)
        self._station_breaker = self._cb_config.get_station_breaker()
        self._payment_breaker = self._cb_config.get_payment_breaker()
        self._profile_breaker = self._cb_config.get_profile_breaker()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retries = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.3,
            status_forcelist=(502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({"User-Agent": "rental-core/1.0"})
        return session

    def _url(self, path: str) -> str:
        return f"{self._external_base.rstrip('/')}/{path.lstrip('/')}"

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        response = self._session.get(
            self._url(path), params=params, timeout=self._timeout
        )
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict) -> dict:
        response = self._session.post(
            self._url(path), json=payload, timeout=self._timeout
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def get_station_data(self, station_id: str) -> StationData:
        @self._station_breaker
        def _get_station_data():
            data = self._get("/station-data", {"id": station_id})
            slots = [
                Slot(index=s["index"], empty=s["empty"], charge=s["charge"])
                for s in data["slots"]
            ]
            return StationData(
                id=station_id,
                tariff_id=data["tariff_id"],
                location=data["location"],
                slots=slots,
            )

        return _get_station_data()

    def get_tariff(self, zone_id: str) -> Tariff:
        @cached(cache=self._tariff_cache)
        def _get_tariff_cached(zone_id: str) -> Tariff:
            @self._station_breaker
            def _get_tariff_data():
                data = self._get("/tariff", {"id": zone_id})
                return Tariff(
                    id=zone_id,
                    price_per_hour=int(data["price_per_hour"]),
                    free_period_min=int(data["free_period_min"]),
                    default_deposit=int(data["default_deposit"]),
                )

            return _get_tariff_data()

        return _get_tariff_cached(zone_id)

    def get_user_profile(self, user_id: str) -> UserProfile:
        @self._profile_breaker
        def _get_user_profile():
            data = self._get("/user-profile", {"id": user_id})
            profile = UserProfile(
                id=user_id,
                has_subscribtion=bool(data["has_subscribtion"]),
                trusted=bool(data["trusted"]),
            )
            setattr(profile, "_from_fallback", False)
            return profile

        try:
            return _get_user_profile()
        except Exception:
            profile = UserProfile(id=user_id, has_subscribtion=False, trusted=False)
            setattr(profile, "_from_fallback", True)
            return profile

    def get_configs(self) -> ConfigMap:
        data = self._get("/configs")
        return ConfigMap(data)

    def eject_powerbank(self, station_id: str) -> EjectResponse:
        @self._station_breaker
        def _eject_powerbank():
            data = self._get("/eject-powerbank", {"station_id": station_id})
            return EjectResponse(
                success=data["success"], powerbank_id=data["powerbank_id"]
            )

        return _eject_powerbank()

    def hold_money_for_order(
        self, user_id: str, order_id: str, amount: int
    ) -> Tuple[bool, Optional[str]]:
        @self._payment_breaker
        def _hold_money():
            self._post(
                "/hold-money-for-order",
                {"user_id": user_id, "order_id": order_id, "amount": amount},
            )
            logger.debug(
                f"Successfully held {amount} for user {user_id}, order {order_id}"
            )
            return True, None

        try:
            return _hold_money()
        except Exception as e:
            error_msg = str(e)
            logger.warning(
                f"Failed to hold {amount} for user {user_id}, order {order_id}: {error_msg}"
            )
            return False, error_msg

    def get_circuit_breaker_stats(self):
        return self._cb_config.get_breaker_stats()

    def clear_money_for_order(
        self, user_id: str, order_id: str, amount: int
    ) -> Tuple[bool, Optional[str]]:
        @self._payment_breaker
        def _clear_money():
            self._post(
                "/clear-money-for-order",
                {"user_id": user_id, "order_id": order_id, "amount": amount},
            )
            logger.debug(
                f"Successfully charged {amount} for user {user_id}, order {order_id}"
            )
            return True, None

        try:
            return _clear_money()
        except Exception as e:
            error_msg = str(e)
            logger.warning(
                f"Failed to charge {amount} for user {user_id}, order {order_id}: {error_msg}"
            )
            return False, error_msg
