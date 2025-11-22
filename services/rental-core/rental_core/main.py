from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from rental_core.api.v1 import health, rentals
from rental_core.clients.external import ExternalClient
from rental_core.config.logging import setup_logging
from rental_core.config.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting rental-core service")

    settings = Settings()
    app.state.external_client = ExternalClient(settings)

    yield
    logger.info("Shutting down rental-core service")


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title="Rental Core Service",
        description="Core service for powerbank rental system",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(rentals.router, prefix="/api/v1", tags=["rentals"])

    return app


def main():
    import uvicorn

    uvicorn.run(
        "rental_core.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None,
    )


app = create_app()


if __name__ == "__main__":
    main()
