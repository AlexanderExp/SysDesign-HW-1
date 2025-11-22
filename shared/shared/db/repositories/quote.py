from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from shared.db.models import Quote


class QuoteRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_quote(
        self,
        quote_id: str,
        user_id: str,
        station_id: str,
        price_per_hour: int,
        free_period_min: int,
        deposit: int,
        expires_at: datetime,
        created_at: Optional[datetime] = None,
    ) -> None:
        if created_at is None:
            created_at = datetime.now()

        quote = Quote(
            id=quote_id,
            user_id=user_id,
            station_id=station_id,
            price_per_hour=price_per_hour,
            free_period_min=free_period_min,
            deposit=deposit,
            expires_at=expires_at,
            created_at=created_at,
        )
        self.session.add(quote)
        self.session.flush()

    def get_quote(self, quote_id: str) -> Optional[Quote]:
        return self.session.get(Quote, quote_id)

    def delete_quote(self, quote_id: str) -> None:
        quote = self.get_quote(quote_id)
        if quote:
            self.session.delete(quote)
            self.session.flush()
