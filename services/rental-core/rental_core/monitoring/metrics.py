from prometheus_client import Counter, Gauge, Histogram, Info
from prometheus_fastapi_instrumentator import Instrumentator

# Business metrics
rentals_total = Counter(
    "rentals_total",
    "Total number of rentals created",
    ["status"],  # ACTIVE, FINISHED, BUYOUT, FAILED
)

quotes_total = Counter("quotes_total", "Total number of quotes created")

rental_duration_seconds = Histogram(
    "rental_duration_seconds",
    "Duration of completed rentals in seconds",
    buckets=[60, 300, 900, 1800, 3600, 7200, 14400, 28800, 86400],  # 1min to 1day
)

active_rentals_gauge = Gauge(
    "active_rentals_current", "Current number of active rentals"
)

# Technical metrics
circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["service"],  # station, payment, profile
)

circuit_breaker_failures = Counter(
    "circuit_breaker_failures_total", "Total circuit breaker failures", ["service"]
)

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

redis_operations = Counter(
    "redis_operations_total",
    "Total Redis operations",
    ["operation", "status"],  # get, set, delete / success, error
)

database_connections = Gauge(
    "database_connections_active", "Active database connections"
)

# Application info
app_info = Info("rental_core_app", "Application information")


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
    app_info.info({"version": version, "service": "rental-core"})
