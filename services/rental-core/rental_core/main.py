from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from rental_core.api.v1 import health, rentals
from rental_core.clients.external import ExternalClient
from rental_core.config.logging import setup_logging
from rental_core.config.settings import Settings
from rental_core.db.database import get_sessionmaker
from rental_core.db.models import Base


def init_database(settings: Settings):
    """Initialize database tables on startup."""
    try:
        sessionmaker = get_sessionmaker(settings)
        session = sessionmaker()
        try:
            bind = session.get_bind()
            Base.metadata.create_all(bind=bind, checkfirst=True)
            logger.info("Database tables initialized successfully")
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting rental-core service")

    settings = Settings()
    
    # Инициализируем БД один раз при старте
    init_database(settings)
    
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

    # Настройка CORS для доступа из UI
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # В production указать конкретные домены
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
