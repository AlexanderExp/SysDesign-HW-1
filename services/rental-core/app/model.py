# services/rental-core/app/model.py
from dataclasses import dataclass
from datetime import datetime

# --- DTO из внешних источников и внутренних вспомогательных структур ---


@dataclass
class Slot:
    index: int
    empty: bool
    charge: int


@dataclass
class StationData:
    id: str
    tariff_id: str
    location: str
    slots: list[Slot]


@dataclass
class Tariff:
    id: str
    price_per_hour: int
    free_period_min: int
    default_deposit: int


@dataclass
class UserProfile:
    id: str
    has_subscribtion: bool
    trusted: bool


class ConfigMap:
    def __init__(self, data: dict):
        self._data = data
        for k, v in data.items():
            setattr(self, k, v)

    def __getattr__(self, item):
        return self._data.get(item, None)


@dataclass
class EjectResponse:
    success: bool
    powerbank_id: str
