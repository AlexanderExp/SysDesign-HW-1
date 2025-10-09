import json
import os
import redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def save(quote_id: str, payload: dict, ttl_sec: int = 60) -> None:
    r.setex(f"offer:{quote_id}", ttl_sec, json.dumps(payload))


def get(quote_id: str) -> dict | None:
    raw = r.get(f"offer:{quote_id}")
    return json.loads(raw) if raw else None


def pop(quote_id: str) -> dict | None:
    key = f"offer:{quote_id}"
    pipe = r.pipeline()
    pipe.get(key)
    pipe.delete(key)
    val, _ = pipe.execute()
    return json.loads(val) if val else None
