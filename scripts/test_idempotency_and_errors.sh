#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib_http.sh"

BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
USER_ID="${USER_ID:-u1}"
STATION_ID="${STATION_ID:-some-station-id}"

echo "== idempotent start =="
QJSON=$(http_post_json "$BASE/api/v1/rentals/quote" \
  "{\"station_id\":\"$STATION_ID\",\"user_id\":\"$USER_ID\"}")
QID=$(echo "$QJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')

IDEMP=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())')
S1=$(http_post_json "$BASE/api/v1/rentals/start" "{\"quote_id\":\"$QID\"}" "Idempotency-Key: $IDEMP")
OID1=$(echo "$S1" | python3 -c 'import sys,json; print(json.load(sys.stdin)["order_id"])')

# Повтор тем же ключом — должен вернуть тот же order_id
S2=$(http_post_json "$BASE/api/v1/rentals/start" "{\"quote_id\":\"$QID\"}" "Idempotency-Key: $IDEMP")
OID2=$(echo "$S2" | python3 -c 'import sys,json; print(json.load(sys.stdin)["order_id"])')

if [ "$OID1" != "$OID2" ]; then
  echo "❌ idempotency expected same order_id, got $OID1 vs $OID2"
  exit 1
fi

echo
echo "== invalid quote -> error =="
# Неверный quote — ожидаем 4xx. Проверим, что сервер отдаёт ошибку, а не 200.
set +e
resp=$(curl -sS -w $'\n%{http_code}' -X POST "$BASE/api/v1/rentals/start" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen 2>/dev/null || python3 - <<<'import uuid; print(uuid.uuid4())')" \
  -d '{"quote_id":"non-existing"}')
code="${resp##*$'\n'}"; body="${resp%$'\n'*}"
set -e
if [[ "$code" =~ ^2 ]]; then
  echo "❌ expected 4xx on invalid quote, got $code"
  echo "$body"
  exit 1
fi

echo "OK"
