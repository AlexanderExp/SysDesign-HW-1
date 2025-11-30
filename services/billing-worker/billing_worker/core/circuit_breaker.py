from typing import Any, Dict

from loguru import logger
from pybreaker import CircuitBreaker, CircuitBreakerListener

from billing_worker.config.settings import Settings
from billing_worker.monitoring.metrics import MetricsCollector


class MetricsCircuitBreakerListener(CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state) -> None:
        logger.warning(
            f"Circuit Breaker '{cb.name}' state changed: {old_state} -> {new_state}. "
            f"Failures: {cb.fail_counter}/{cb.fail_max}"
        )

        MetricsCollector.record_circuit_breaker_state(cb.name, new_state)

    def failure(self, cb, exc) -> None:  # noqa: ARG002
        MetricsCollector.record_circuit_breaker_failure(cb.name)


class LoggingListener(CircuitBreakerListener):
    """Listener для логирования изменений состояния circuit breaker'а.

    Наследуемся от CircuitBreakerListener, чтобы у него были все
    нужные методы (before_call, after_call, failure, state_change, ...).
    """

    def state_change(self, cb: CircuitBreaker, old_state: str, new_state: str) -> None:  # type: ignore[override]
        logger.warning(
            "Circuit Breaker '%s' state changed: %s -> %s. Failures: %s/%s",
            cb.name,
            old_state,
            new_state,
            cb.fail_counter,
            cb.fail_max,
        )


class CircuitBreakerConfig:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._listener = MetricsCircuitBreakerListener()

    def get_payment_breaker(self) -> CircuitBreaker:
        """Circuit breaker для платежных операций.

        ВАЖНО: возвращаем ИМЕННО экземпляр CircuitBreaker.
        """
        if "payment" not in self._breakers:
            self._breakers["payment"] = CircuitBreaker(
                fail_max=self.settings.cb_payment_fail_max,
                reset_timeout=self.settings.cb_payment_reset_timeout,
                name="payment_operations",
                listeners=[self._listener],
            )
        return self._breakers["payment"]

    def get_breaker_stats(self) -> Dict[str, Dict[str, Any]]:
        stats: Dict[str, Dict[str, Any]] = {}
        for name, breaker in self._breakers.items():
            stats[name] = {
                "state": str(breaker.current_state),
                "fail_counter": breaker.fail_counter,
                "fail_max": breaker.fail_max,
                "reset_timeout": breaker.reset_timeout,
                "last_failure": getattr(breaker, "last_failure", None),
            }
        return stats
