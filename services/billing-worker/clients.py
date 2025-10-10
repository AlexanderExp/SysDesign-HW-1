# services/billing-worker/clients.py
import os
import requests

EXTERNAL_BASE = os.getenv("EXTERNAL_BASE", "http://external-stubs:3629")
HTTP_TIMEOUT_SEC = float(os.getenv("HTTP_TIMEOUT_SEC", "2.5"))

_s = requests.Session()
_s.headers.update({"User-Agent": "billing-worker/1.0"})


def _post(path: str, payload: dict):
    r = _s.post(EXTERNAL_BASE + path, json=payload, timeout=HTTP_TIMEOUT_SEC)
    r.raise_for_status()
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else None


def clear_money_for_order(user_id: str, order_id: str, amount: int):
    _post("/clear-money-for-order",
          {"user_id": user_id, "order_id": order_id, "amount": amount})
