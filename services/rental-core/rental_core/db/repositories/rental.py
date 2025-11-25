from typing import Optional

from shared.db.models import Rental
from shared.db.repositories.rental import RentalRepository as SharedRentalRepository

from rental_core.schemas import RentalData


class RentalRepository(SharedRentalRepository):
    def get_rental(self, rental_id: str) -> Optional[Rental]:
        return self.get_by_id(rental_id)

    def get_rental_data(self, rental_id: str) -> Optional[RentalData]:
        rental = self.get_rental(rental_id)
        if not rental:
            return None

        return RentalData(
            id=rental.id,
            user_id=rental.user_id,
            powerbank_id=rental.powerbank_id,
            price_per_hour=rental.price_per_hour,
            free_period_min=rental.free_period_min,
            deposit=rental.deposit,
            status=rental.status,
            total_amount=rental.total_amount,
            started_at=rental.started_at,
            finished_at=rental.finished_at,
        )


__all__ = ["RentalRepository"]
