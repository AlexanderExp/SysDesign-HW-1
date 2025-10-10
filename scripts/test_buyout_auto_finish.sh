#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib_http.sh"

BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
USER_ID="${USER_ID:-u1}"
STATION_ID="${STATION_ID:-some-station-id}"
TICK="${BILLING_TICK_SEC:-10}"
R_BUYOUT="${R_BUYOUT:-500}"

echo "== health =="
http_get_json "$BASE/health" >/dev/null
echo "✅ rental-core alive"

echo
echo "== start short rental =="
QJSON=$(http_post_json "$BASE/rentals/quote" \
  "{\"station_id\":\"$STATION_ID\",\"user_id\":\"$USER_ID\"}")
QID=$(echo "$QJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')
IDEMP=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())')
SJSON=$(http_post_json "$BASE/rentals/start" \
  "{\"quote_id\":\"$QID\"}" \
  "Idempotency-Key: $IDEMP")
OID=$(echo "$SJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["order_id"])')

# Форсим быстрый buyout: уменьшим порог и «прокрутим» время
# (в биллинг-воркере R_BUYOUT считывается из env при старте — перед прогоном suite задайте низкое значение)
FF_MIN=${FF_MINUTES:-65}
docker compose exec -T db psql -U app -d rental -c \
"update rentals set started_at = now() - interval '${FF_MIN} minutes', status='ACTIVE' where id='${OID}';" | cat

WAIT=$(( TICK*4 ))
echo
echo "== wait ~${WAIT}s (tick=$TICK) =="
sleep "$WAIT"

echo
echo "== status =="
STAT=$(http_get_json "$BASE/rentals/${OID}/status")
echo "$STAT" | python3 -m json.tool
STATUS=$(echo "$STAT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')

if [ "$STATUS" = "BUYOUT" ] || [ "$STATUS" = "FINISHED" ]; then
  echo "OK"
else
  echo "❌ expected BUYOUT/FINISHED, got $STATUS"
  exit 1
fi
