#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib_http.sh"

BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
USER_ID="${USER_ID:-u1}"
STATION_ID="${STATION_ID:-some-station-id}"

echo "== health =="
http_get_json "$BASE/api/v1/health" >/dev/null
echo "✅ rental-core alive"

echo
echo "== fresh quote =="
QJSON=$(http_post_json "$BASE/api/v1/rentals/quote" \
  "{\"station_id\":\"$STATION_ID\",\"user_id\":\"$USER_ID\"}")
echo "$QJSON" | python3 -m json.tool
QID=$(echo "$QJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')

# Насильно протухаем оффер в БД
echo
echo "== expire quote in DB =="
docker compose exec -T db psql -U app -d rental -c \
"update quotes set expires_at = now() - interval '5 minutes' where id='${QID}';" | cat

echo
echo "== start with expired quote -> expect 4xx =="
set +e
resp=$(curl -sS -w $'\n%{http_code}' -X POST "$BASE/api/v1/rentals/start" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen 2>/dev/null || python3 - <<<'import uuid; print(uuid.uuid4())')" \
  -d "{\"quote_id\":\"${QID}\"}")
code="${resp##*$'\n'}"; body="${resp%$'\n'*}"
set -e

if [[ "$code" =~ ^2 ]]; then
  echo "❌ expected 4xx on expired quote, got $code"
  echo "$body"
  exit 1
fi

echo "OK"
