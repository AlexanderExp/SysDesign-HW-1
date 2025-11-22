from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_sessionmaker(database_url: str) -> sessionmaker:
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


def get_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True, future=True)
