from fastapi import APIRouter, Depends

from rental_core.schemas import HealthResponse
from rental_core.clients.external import ExternalClient
from rental_core.config.settings import Settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(ok=True)


@router.get("/health/circuit-breakers")
def circuit_breaker_health():
    settings = Settings()
    external_client = ExternalClient(settings)
    return {
        "circuit_breakers": external_client.get_circuit_breaker_stats(),
        "status": "ok"
    }
