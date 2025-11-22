import json
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4 as _uuid4


def uuid4() -> str:
    return str(_uuid4())


def json_default(o):
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return str(o)


def json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=json_default)
