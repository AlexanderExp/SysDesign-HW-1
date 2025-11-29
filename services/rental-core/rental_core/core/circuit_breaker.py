from typing import Dict, Any
from pybreaker import CircuitBreaker
from loguru import logger

from rental_core.config.settings import Settings


class CircuitBreakerConfig:    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def get_station_breaker(self) -> CircuitBreaker:
        if "station" not in self._breakers:
            self._breakers["station"] = CircuitBreaker(
                fail_max=self.settings.cb_station_fail_max,
                reset_timeout=self.settings.cb_station_reset_timeout,
                exclude=[KeyError, ValueError],  # Don't count data validation errors
                name="station_operations",
                listeners=[self._log_state_change]
            )
        return self._breakers["station"]
    
    def get_payment_breaker(self) -> CircuitBreaker:
        if "payment" not in self._breakers:
            self._breakers["payment"] = CircuitBreaker(
                fail_max=self.settings.cb_payment_fail_max,
                reset_timeout=self.settings.cb_payment_reset_timeout,
                name="payment_operations",
                listeners=[self._log_state_change]
            )
        return self._breakers["payment"]
    
    def get_profile_breaker(self) -> CircuitBreaker:
        if "profile" not in self._breakers:
            self._breakers["profile"] = CircuitBreaker(
                fail_max=self.settings.cb_profile_fail_max,
                reset_timeout=self.settings.cb_profile_reset_timeout,
                exclude=[KeyError, ValueError],  # Don't count data validation errors
                name="profile_operations",
                listeners=[self._log_state_change]
            )
        return self._breakers["profile"]
    
    def _log_state_change(self, breaker: CircuitBreaker, old_state: str, new_state: str) -> None:
        logger.warning(
            f"Circuit Breaker '{breaker.name}' state changed: {old_state} -> {new_state}. "
            f"Failures: {breaker.fail_counter}/{breaker.fail_max}"
        )
    
    def get_breaker_stats(self) -> Dict[str, Dict[str, Any]]:
        stats = {}
        for name, breaker in self._breakers.items():
            stats[name] = {
                "state": breaker.current_state,
                "fail_counter": breaker.fail_counter,
                "fail_max": breaker.fail_max,
                "reset_timeout": breaker.reset_timeout,
                "last_failure": getattr(breaker, "last_failure", None)
            }
        return stats