from prometheus_client import Counter, Gauge, Histogram, Info, start_http_server

# Business metrics - Billing Worker specific
billing_cycles_total = Counter(
    "rental_system_billing_cycles_total",
    "Total number of billing cycles processed",
    ["service"]  # service=billing-worker
)

payment_attempts_total = Counter(
    "rental_system_payment_attempts_total",
    "Total payment attempts",
    ["service", "status"],  # service=billing-worker, status=success/failure
)

payment_amount_total = Counter(
    "rental_system_payment_amount_total",
    "Total payment amount processed in kopecks",
    ["service", "status"],  # service=billing-worker, status=success/failure
)

debt_amount_gauge = Gauge(
    "rental_system_debt_amount_current",
    "Current total debt amount in kopecks",
    ["service"]  # service=billing-worker
)

debt_operations_total = Counter(
    "rental_system_debt_operations_total",
    "Total debt operations",
    ["service", "operation"],  # service=billing-worker, operation=add/reduce/retry
)

active_rentals_processed = Gauge(
    "rental_system_active_rentals_processed_last_cycle",
    "Number of active rentals processed in last billing cycle",
    ["service"]  # service=billing-worker
)

billing_cycle_duration = Histogram(
    "rental_system_billing_cycle_duration_seconds",
    "Duration of billing cycle processing",
    ["service"],  # service=billing-worker
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# Technical metrics - shared across services (same as rental-core)
external_api_requests = Counter(
    "rental_system_external_api_requests_total",
    "Total external API requests",
    ["service", "api_service", "endpoint", "status"],  # service=billing-worker
)

external_api_duration = Histogram(
    "rental_system_external_api_duration_seconds",
    "External API request duration",
    ["service", "api_service", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

circuit_breaker_state = Gauge(
    "rental_system_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["service", "circuit_name"],  # service=billing-worker, circuit_name=payment
)

circuit_breaker_failures = Counter(
    "rental_system_circuit_breaker_failures_total",
    "Total circuit breaker failures",
    ["service", "circuit_name"]
)

database_connections = Gauge(
    "rental_system_database_connections_active",
    "Active database connections",
    ["service", "database"]  # service=billing-worker, database=billing
)

database_query_duration = Histogram(
    "rental_system_database_query_duration_seconds",
    "Database query duration",
    ["service", "database", "operation"],  # operation=select/insert/update/delete
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

worker_errors_total = Counter(
    "rental_system_worker_errors_total",
    "Total worker errors",
    ["service", "error_type"]  # service=billing-worker
)

# Application info
app_info = Info("rental_system_app_info", "Application information")


def init_app_info(version: str = "1.0.0"):
    app_info.info({"version": version, "service": "billing-worker", "component": "worker"})


def start_metrics_server(port: int = 8001):
    start_http_server(port)


class MetricsCollector:
    SERVICE_NAME = "billing-worker"
    
    @staticmethod
    def record_payment_attempt(success: bool, amount: int):
        status = "success" if success else "failure"
        payment_attempts_total.labels(service=MetricsCollector.SERVICE_NAME, status=status).inc()
        payment_amount_total.labels(service=MetricsCollector.SERVICE_NAME, status=status).inc(amount)

    @staticmethod
    def record_debt_operation(operation: str, amount: int = 0):
        debt_operations_total.labels(service=MetricsCollector.SERVICE_NAME, operation=operation).inc()
        if operation == "add":
            debt_amount_gauge.labels(service=MetricsCollector.SERVICE_NAME).inc(amount)
        elif operation == "reduce":
            debt_amount_gauge.labels(service=MetricsCollector.SERVICE_NAME).dec(amount)

    @staticmethod
    def record_billing_cycle(duration: float, active_rentals: int):
        billing_cycles_total.labels(service=MetricsCollector.SERVICE_NAME).inc()
        billing_cycle_duration.labels(service=MetricsCollector.SERVICE_NAME).observe(duration)
        active_rentals_processed.labels(service=MetricsCollector.SERVICE_NAME).set(active_rentals)

    @staticmethod
    def record_external_api_call(
        api_service: str, endpoint: str, duration: float, success: bool
    ):
        status = "success" if success else "error"
        external_api_requests.labels(
            service=MetricsCollector.SERVICE_NAME,
            api_service=api_service,
            endpoint=endpoint,
            status=status
        ).inc()
        external_api_duration.labels(
            service=MetricsCollector.SERVICE_NAME,
            api_service=api_service,
            endpoint=endpoint
        ).observe(duration)

    @staticmethod
    def record_circuit_breaker_state(circuit_name: str, state: str):
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
        circuit_breaker_state.labels(
            service=MetricsCollector.SERVICE_NAME,
            circuit_name=circuit_name
        ).set(state_value)

    @staticmethod
    def record_circuit_breaker_failure(circuit_name: str):
        circuit_breaker_failures.labels(
            service=MetricsCollector.SERVICE_NAME,
            circuit_name=circuit_name
        ).inc()

    @staticmethod
    def record_database_query(database: str, operation: str, duration: float):
        database_query_duration.labels(
            service=MetricsCollector.SERVICE_NAME,
            database=database,
            operation=operation
        ).observe(duration)

    @staticmethod
    def record_worker_error(error_type: str):
        worker_errors_total.labels(
            service=MetricsCollector.SERVICE_NAME,
            error_type=error_type
        ).inc()
        
    @staticmethod
    def record_database_connections(database: str, count: int):
        database_connections.labels(
            service=MetricsCollector.SERVICE_NAME,
            database=database
        ).set(count)
