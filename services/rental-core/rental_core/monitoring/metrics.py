from prometheus_client import Counter, Gauge, Histogram, Info
from prometheus_fastapi_instrumentator import Instrumentator

# Business metrics - Rental Core specific
rentals_total = Counter(
    "rental_system_rentals_total",
    "Total number of rentals created",
    ["service", "status"],  # service=rental-core, status=ACTIVE/FINISHED/BUYOUT/FAILED
)

quotes_total = Counter(
    "rental_system_quotes_total",
    "Total number of quotes created",
    ["service"],  # service=rental-core
)

rental_duration_seconds = Histogram(
    "rental_system_rental_duration_seconds",
    "Duration of completed rentals in seconds",
    ["service"],  # service=rental-core
    buckets=[60, 300, 900, 1800, 3600, 7200, 14400, 28800, 86400],  # 1min to 1day
)

active_rentals_gauge = Gauge(
    "rental_system_active_rentals_current",
    "Current number of active rentals",
    ["service"],  # service=rental-core
)

# Technical metrics - shared across services
circuit_breaker_state = Gauge(
    "rental_system_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    [
        "service",
        "circuit_name",
    ],  # service=rental-core/billing-worker, circuit_name=station/payment/profile
)

circuit_breaker_failures = Counter(
    "rental_system_circuit_breaker_failures_total",
    "Total circuit breaker failures",
    ["service", "circuit_name"],
)

external_api_requests = Counter(
    "rental_system_external_api_requests_total",
    "Total external API requests",
    [
        "service",
        "api_service",
        "endpoint",
        "status",
    ],  # service=rental-core/billing-worker
)

external_api_duration = Histogram(
    "rental_system_external_api_duration_seconds",
    "External API request duration",
    ["service", "api_service", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

database_connections = Gauge(
    "rental_system_database_connections_active",
    "Active database connections",
    [
        "service",
        "database",
    ],  # service=rental-core/billing-worker, database=rental/billing
)

database_query_duration = Histogram(
    "rental_system_database_query_duration_seconds",
    "Database query duration",
    ["service", "database", "operation"],  # operation=select/insert/update/delete
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# Application info
app_info = Info("rental_system_app_info", "Application information")


def setup_instrumentator() -> Instrumentator:
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/health"],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )

    # Add default HTTP metrics - if no add() is called, default metrics are added automatically
    # We can add custom metrics here if needed:
    # instrumentator.add(metrics.latency())
    # instrumentator.add(metrics.request_size())
    # instrumentator.add(metrics.response_size())

    return instrumentator


def init_app_info(version: str = "1.0.0"):
    app_info.info({"version": version, "service": "rental-core", "component": "api"})
