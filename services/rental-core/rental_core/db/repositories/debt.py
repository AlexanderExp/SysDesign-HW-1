from typing import Optional

from shared.db.repositories.debt import DebtRepository as SharedDebtRepository

from rental_core.schemas import DebtData


class DebtRepository(SharedDebtRepository):
    def get_debt_amount(self, rental_id: str) -> int:
        return self.get_amount(rental_id)

    def get_debt(self, rental_id: str) -> Optional[DebtData]:
        debt = self.get_by_rental_id(rental_id)
        if not debt:
            return None

        return DebtData(
            rental_id=debt.rental_id,
            amount_total=debt.amount_total,
            updated_at=debt.updated_at,
            attempts=debt.attempts,
            last_attempt_at=debt.last_attempt_at,
        )


__all__ = ["DebtRepository"]
