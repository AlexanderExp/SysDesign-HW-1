from shared.db.database import get_sessionmaker as shared_get_sessionmaker

from billing_worker.config.settings import Settings


def get_sessionmaker(settings: Settings):
    return shared_get_sessionmaker(settings.database_url)
