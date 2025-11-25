import json
from typing import Optional

from sqlalchemy.orm import Session

from shared.db.models import IdempotencyKey


class IdempotencyRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_idempotency_key(self, key: str) -> Optional[IdempotencyKey]:
        return self.session.get(IdempotencyKey, key)

    def create_idempotency_key(
        self, key: str, scope: str, user_id: str, response_data: dict
    ) -> None:
        idempotency_key = IdempotencyKey(
            key=key,
            scope=scope,
            user_id=user_id,
            response_json=json.dumps(response_data, ensure_ascii=False),
        )
        self.session.add(idempotency_key)
        self.session.flush()

    def get_cached_response(self, key: str) -> Optional[dict]:
        record = self.get_idempotency_key(key)
        if record:
            return json.loads(record.response_json)
        return None
