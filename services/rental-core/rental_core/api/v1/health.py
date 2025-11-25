from fastapi import APIRouter

from rental_core.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(ok=True)
