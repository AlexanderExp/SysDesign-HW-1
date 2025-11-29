from typing import Dict, Any

import pybreaker
from loguru import logger

from billing_worker.config.settings import Settings


class LoggingCircuitBreakerListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state) -> None:
        logger.warning(
            f"Circuit Breaker '{cb.name}' state changed: {old_state} -> {new_state}. "
            f"Failures: {cb.fail_counter}/{cb.fail_max}"
        )


class CircuitBreakerConfig:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._breakers: Dict[str, pybreaker.CircuitBreaker] = {}

    def get_payment_breaker(self) -> pybreaker.CircuitBreaker:
        if "payment" not in self._breakers:
            self._breakers["payment"] = pybreaker.CircuitBreaker(
                fail_max=self._settings.cb_payment_fail_max,
                reset_timeout=self._settings.cb_payment_reset_timeout,
                name="billing_payment",
                listeners=[LoggingCircuitBreakerListener()],
            )
        return self._breakers["payment"]

    def get_breaker_stats(self) -> Dict[str, Dict[str, Any]]:
        stats: Dict[str, Dict[str, Any]] = {}
        for name, breaker in self._breakers.items():
            stats[name] = {
                "state": breaker.current_state,
                "fail_counter": breaker.fail_counter,
                "fail_max": breaker.fail_max,
                "reset_timeout": breaker.reset_timeout,
                "last_failure": getattr(breaker, "last_failure", None),
            }
        return stats
