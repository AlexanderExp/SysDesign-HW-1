from typing import Optional

from shared.db.repositories.quote import QuoteRepository as SharedQuoteRepository

from rental_core.schemas import QuoteData


class QuoteRepository(SharedQuoteRepository):
    def get_quote(self, quote_id: str) -> Optional[QuoteData]:
        quote = super().get_quote(quote_id)
        if not quote:
            return None

        return QuoteData(
            id=quote.id,
            user_id=quote.user_id,
            station_id=quote.station_id,
            price_per_hour=quote.price_per_hour,
            free_period_min=quote.free_period_min,
            deposit=quote.deposit,
            expires_at=quote.expires_at,
            created_at=quote.created_at,
        )

    def delete_quote(self, quote_id: str) -> None:
        quote = super().get_quote(quote_id)
        if quote:
            self.session.delete(quote)
            self.session.flush()


__all__ = ["QuoteRepository"]
