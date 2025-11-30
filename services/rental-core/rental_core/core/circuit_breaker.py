from typing import Any, Dict

import pybreaker
from loguru import logger

from rental_core.config.settings import Settings
from rental_core.monitoring.metrics import (
    circuit_breaker_failures,
    circuit_breaker_state,
)


class LoggingCircuitBreakerListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state) -> None:
        logger.warning(
            f"Circuit Breaker '{cb.name}' state changed: {old_state} -> {new_state}. "
            f"Failures: {cb.fail_counter}/{cb.fail_max}"
        )

        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(new_state, 0)
        circuit_breaker_state.labels(service="rental-core", circuit_name=cb.name).set(
            state_value
        )

    def failure(self, cb, exc) -> None:  # noqa: ARG002
        circuit_breaker_failures.labels(
            service="rental-core", circuit_name=cb.name
        ).inc()

    # если они не нужны – базовый класс оставит их no-op


class CircuitBreakerConfig:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._breakers: Dict[str, pybreaker.CircuitBreaker] = {}
        self._listener = LoggingCircuitBreakerListener()

    def _make_breaker(
        self,
        name: str,
        fail_max: int,
        reset_timeout: int,
        exclude: tuple[type[BaseException], ...] = (),
    ) -> pybreaker.CircuitBreaker:
        return pybreaker.CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            exclude=exclude,
            name=name,
            listeners=[self._listener],  # ✅ объект-listener, а не функция
        )

    def get_station_breaker(self) -> pybreaker.CircuitBreaker:
        if "station" not in self._breakers:
            self._breakers["station"] = self._make_breaker(
                name="station_operations",
                fail_max=self.settings.cb_station_fail_max,
                reset_timeout=self.settings.cb_station_reset_timeout,
                exclude=(KeyError, ValueError),
            )
        return self._breakers["station"]

    def get_payment_breaker(self) -> pybreaker.CircuitBreaker:
        if "payment" not in self._breakers:
            self._breakers["payment"] = self._make_breaker(
                name="payment_operations",
                fail_max=self.settings.cb_payment_fail_max,
                reset_timeout=self.settings.cb_payment_reset_timeout,
            )
        return self._breakers["payment"]

    def get_profile_breaker(self) -> pybreaker.CircuitBreaker:
        if "profile" not in self._breakers:
            self._breakers["profile"] = self._make_breaker(
                name="profile_operations",
                fail_max=self.settings.cb_profile_fail_max,
                reset_timeout=self.settings.cb_profile_reset_timeout,
                exclude=(KeyError, ValueError),
            )
        return self._breakers["profile"]

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
