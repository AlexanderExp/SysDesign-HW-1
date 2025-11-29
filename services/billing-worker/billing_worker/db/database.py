from sqlalchemy.orm import sessionmaker

from shared.db.database import get_sessionmaker as shared_get_sessionmaker
from billing_worker.config.settings import Settings


def get_rental_sessionmaker(settings: Settings) -> sessionmaker:
    return shared_get_sessionmaker(settings.database_url)


def get_billing_sessionmaker(settings: Settings) -> sessionmaker:
    return shared_get_sessionmaker(settings.billing_database_url)
