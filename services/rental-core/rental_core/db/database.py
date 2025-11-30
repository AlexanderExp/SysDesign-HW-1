from shared.db.database import get_engine as shared_get_engine
from shared.db.database import get_sessionmaker as shared_get_sessionmaker

from rental_core.config.settings import Settings


def get_sessionmaker(settings: Settings):
    return shared_get_sessionmaker(settings.database_url)


def get_billing_sessionmaker(settings: Settings):
    return shared_get_sessionmaker(settings.billing_database_url)


def get_engine(settings: Settings):
    return shared_get_engine(settings.database_url)
