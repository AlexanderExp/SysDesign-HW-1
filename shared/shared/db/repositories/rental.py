import math
from datetime import datetime, timezone
from typing import List, Optional

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from shared.db.models import Rental


class RentalRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, rental_id: str) -> Optional[Rental]:
        return self.session.get(Rental, rental_id)

    def create_rental(self, rental: Rental) -> None:
        self.session.add(rental)
        self.session.flush()

    def update_rental(self, rental: Rental) -> None:
        self.session.merge(rental)
        self.session.flush()

    def get_active_rental_ids(self) -> List[str]:
            result = (
                self.session.execute(select(Rental.id).where(Rental.status == "ACTIVE"))
                .scalars()
                .all()
            )
            ids = list(result)
            logger.info(f"[DEBUG] Active rentals from {self.session.bind.url}: {ids}")
            return ids

    def update_total_amount(self, rental_id: str, amount_delta: int) -> bool:
        rental = self.get_by_id(rental_id)
        if not rental:
            return False

        old_amount = rental.total_amount or 0
        rental.total_amount = old_amount + amount_delta
        logger.debug(
            f"Updated rental {rental_id} total_amount: {old_amount} -> {rental.total_amount}"
        )
        return True

    def finish_rental(self, rental_id: str, status: str = "FINISHED") -> bool:
        now = datetime.now(timezone.utc)
        result = self.session.execute(
            update(Rental)
            .where(Rental.id == rental_id, Rental.status == "ACTIVE")
            .values(status=status, finished_at=now)
        )

        updated = result.rowcount > 0
        if updated:
            logger.info(f"Finished rental {rental_id} with status {status}")
        return updated

    def set_buyout_status(self, rental_id: str) -> bool:
        return self.finish_rental(rental_id, "BUYOUT")

    def calculate_due_amount(self, rental: Rental, current_time: datetime) -> int:
        if not rental.started_at:
            return 0

        # Ensure timezone awareness
        start_time = rental.started_at
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        total_seconds = int((current_time - start_time).total_seconds())
        free_seconds = rental.free_period_min * 60
        billable_seconds = max(0, total_seconds - free_seconds)

        # Calculate amount: (price_per_hour * billable_seconds) / 3600
        if billable_seconds > 0:
            due_amount = math.ceil((rental.price_per_hour * billable_seconds) / 3600)
        else:
            due_amount = 0
        return due_amount
