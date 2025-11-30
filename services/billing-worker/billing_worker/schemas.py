from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class RentalBillingResult:
    charged_amount: int
    debt_delta: int


@dataclass
class BillingTickResult:
    active_rentals: int
    total_charged: int
    total_debt_delta: int


dataclass


class AllRentalsBillingResult(BaseModel):
    active_rentals: int
    total_charged: int
    total_debt_delta: int
