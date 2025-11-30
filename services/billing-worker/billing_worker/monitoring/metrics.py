from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server

# Business metrics
billing_cycles_total = Counter(
    "billing_cycles_total", "Total number of billing cycles processed"
)

payment_attempts_total = Counter(
    "payment_attempts_total",
    "Total payment attempts",
    ["status"],  # success, failure
)

payment_amount_total = Counter(
    "payment_amount_total",
    "Total payment amount processed in kopecks",
    ["status"],  # success, failure
)

debt_amount_gauge = Gauge("debt_amount_current", "Current total debt amount in kopecks")

debt_operations_total = Counter(
    "debt_operations_total",
    "Total debt operations",
    ["operation"],  # add, reduce, retry
)

active_rentals_processed = Gauge(
    "active_rentals_processed_last_cycle",
    "Number of active rentals processed in last billing cycle",
)

billing_cycle_duration = Histogram(
    "billing_cycle_duration_seconds",
    "Duration of billing cycle processing",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# Technical metrics
external_api_requests = Counter(
    "external_api_requests_total",
    "Total external API requests",
    ["service", "endpoint", "status"],
)

external_api_duration = Histogram(
    "external_api_duration_seconds",
    "External API request duration",
    ["service", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["service"],  # payment
)

circuit_breaker_failures = Counter(
    "circuit_breaker_failures_total", "Total circuit breaker failures", ["service"]
)

database_connections = Gauge(
    "database_connections_active", "Active database connections"
)

database_query_duration = Histogram(
    "database_query_duration_seconds",
    "Database query duration",
    ["operation"],  # select, insert, update, delete
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

worker_errors_total = Counter(
    "worker_errors_total", "Total worker errors", ["error_type"]
)

# Application info
app_info = Info("billing_worker_app", "Application information")


def init_app_info(version: str = "1.0.0"):
    app_info.info({"version": version, "service": "billing-worker"})


def start_metrics_server(port: int = 8001):
    start_http_server(port)


class MetricsCollector:
    @staticmethod
    def record_payment_attempt(success: bool, amount: int):
        status = "success" if success else "failure"
        payment_attempts_total.labels(status=status).inc()
        payment_amount_total.labels(status=status).inc(amount)

    @staticmethod
    def record_debt_operation(operation: str, amount: int = 0):
        debt_operations_total.labels(operation=operation).inc()
        if operation == "add":
            debt_amount_gauge.inc(amount)
        elif operation == "reduce":
            debt_amount_gauge.dec(amount)

    @staticmethod
    def record_billing_cycle(duration: float, active_rentals: int):
        billing_cycles_total.inc()
        billing_cycle_duration.observe(duration)
        active_rentals_processed.set(active_rentals)

    @staticmethod
    def record_external_api_call(
        service: str, endpoint: str, duration: float, success: bool
    ):
        status = "success" if success else "error"
        external_api_requests.labels(
            service=service, endpoint=endpoint, status=status
        ).inc()
        external_api_duration.labels(service=service, endpoint=endpoint).observe(
            duration
        )

    @staticmethod
    def record_circuit_breaker_state(service: str, state: str):
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
        circuit_breaker_state.labels(service=service).set(state_value)

    @staticmethod
    def record_circuit_breaker_failure(service: str):
        circuit_breaker_failures.labels(service=service).inc()

    @staticmethod
    def record_database_query(operation: str, duration: float):
        database_query_duration.labels(operation=operation).observe(duration)

    @staticmethod
    def record_worker_error(error_type: str):
        worker_errors_total.labels(error_type=error_type).inc()
