from pydantic import BaseModel


class RentalBillingResult(BaseModel):
    charged_amount: int
    debt_delta: int


class AllRentalsBillingResult(BaseModel):
    active_rentals: int
    total_charged: int
    total_debt_delta: int
