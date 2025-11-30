from typing import Optional, Tuple

import requests
from loguru import logger

from billing_worker.config.settings import Settings
from billing_worker.core.circuit_breaker import CircuitBreakerConfig


class ExternalClient:
    def __init__(self, settings: Settings):
        # HTTP client
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "billing-worker/1.0"})
        self._timeout = settings.http_timeout_sec
        self._external_base = settings.external_base

        # Circuit breaker for payments
        self._cb_config = CircuitBreakerConfig(settings)
        self._payment_breaker = self._cb_config.get_payment_breaker()

    def _post(self, path: str, payload: dict):
        """
        Low-level POST helper.
        """
        url = f"{self._external_base.rstrip('/')}/{path.lstrip('/')}"
        response = self._session.post(url, json=payload, timeout=self._timeout)
        response.raise_for_status()
        return response.json() if response.content else {}

    def clear_money_for_order(
        self, user_id: str, order_id: str, amount: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Try to charge money for an order via external service.
        Returns (success, error_message).
        """
        @self._payment_breaker
        def _clear_money():
            self._post(
                "/clear-money-for-order",
                {"user_id": user_id, "order_id": order_id, "amount": amount},
            )
            logger.debug(
                "Successfully charged %s for user %s, order %s",
                amount,
                user_id,
                order_id,
            )
            return True, None

        try:
            return _clear_money()
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            logger.warning(
                "Failed to charge %s for user %s, order %s: %s",
                amount,
                user_id,
                order_id,
                error_msg,
            )
            return False, error_msg

    def get_circuit_breaker_stats(self):
        return self._cb_config.get_breaker_stats()
