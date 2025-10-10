import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://app:app@db:5432/rental")


class Base(DeclarativeBase):
    pass


engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False,
    expire_on_commit=False, future=True
)


def init_db():
    from .models import Rental, IdempotencyKey, PaymentAttempt, Debt
    Base.metadata.create_all(bind=engine)
