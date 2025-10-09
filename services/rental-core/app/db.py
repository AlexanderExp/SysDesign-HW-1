import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://app:app@db:5432/rental")


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, future=True)


def init_db():
    # импорт здесь, чтобы избежать циклов
    from .models import Rental
    Base.metadata.create_all(bind=engine)
