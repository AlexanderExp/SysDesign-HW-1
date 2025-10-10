import json
import redis
from typing import Optional
from .config import REDIS_URL, OFFER_TTL_SEC

_r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

_PREFIX = "quote:"


def save_quote(quote_id: str, payload: dict, ttl_sec: int = OFFER_TTL_SEC) -> None:
    key = f"{_PREFIX}{quote_id}"
    _r.setex(key, ttl_sec, json.dumps(payload))


def pop_quote(quote_id: str) -> Optional[dict]:
    key = f"{_PREFIX}{quote_id}"
    pipe = _r.pipeline()
    pipe.get(key)
    pipe.delete(key)
    val, _ = pipe.execute()
    if not val:
        return None
    return json.loads(val)
