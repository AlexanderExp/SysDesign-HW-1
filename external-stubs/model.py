from dataclasses import dataclass
from datetime import datetime

# Содержит в себе DTO (data transfer objects) / данные, получаемые из внешних источников


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


@dataclass
class OfferData:
    id: str
    user_id: str
    station_id: str
    price_per_hour: int
    free_period_min: int
    deposit: int


@dataclass
class OrderData:
    id: str
    user_id: str
    start_station_id: str
    finish_station_id: str
    price_per_hour: int
    free_period_min: int
    deposit: int
    total_amount: int
    start_time: datetime
    finish_time: datetime


class ConfigMap:
    def __init__(self, data: dict):
        self._data = data
        for k, v in data.items():
            self.__setattr__(k, v)

    def __getattr__(self, item):
        return self._data.get(item, None)


@dataclass
class EjectResponse:
    success: bool
    powerbank_id: str
