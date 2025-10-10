# app/tariff_cache.py
import os
from cachetools import TTLCache
from threading import RLock

TTL_SEC = int(os.getenv("TARIFF_TTL_SEC", "600"))  # по умолчанию 10 мин
MAXSIZE = int(os.getenv("TARIFF_CACHE_SIZE", "512"))
cache = TTLCache(maxsize=MAXSIZE, ttl=TTL_SEC)
lock = RLock()


def get_cached(key):
    with lock:
        return cache.get(key)


def put_cached(key, value):
    with lock:
        cache[key] = value
