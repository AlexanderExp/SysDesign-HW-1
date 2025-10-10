#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib_http.sh"

BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
USER_ID="${USER_ID:-u1}"
STATION_ID="${STATION_ID:-some-station-id}"
TICK="${BILLING_TICK_SEC:-10}"

echo "== health =="
http_get_json "$BASE/health" >/dev/null
echo "✅ rental-core alive"

echo
echo "== quote =="
QJSON=$(http_post_json "$BASE/rentals/quote" \
  "{\"station_id\":\"$STATION_ID\",\"user_id\":\"$USER_ID\"}")
echo "$QJSON" | python3 -m json.tool
QID=$(echo "$QJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')

IDEMP=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())')
echo "Idempotency-Key: $IDEMP"

echo
echo "== start =="
SJSON=$(http_post_json "$BASE/rentals/start" \
  "{\"quote_id\":\"$QID\"}" \
  "Idempotency-Key: $IDEMP")
echo "$SJSON" | python3 -m json.tool
OID=$(echo "$SJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["order_id"])')

# Подождём немного, чтобы воркер успел сделать начисления
WAIT=$(( TICK*3 + TICK/2 ))
echo
echo "== wait ~${WAIT}s (tick=$TICK) =="
sleep "$WAIT"

echo
echo "== attempts / debt =="
docker compose exec -T db psql -U app -d rental -c \
"select count(*) attempts_total,
        sum(case when success then 1 else 0 end) attempts_ok,
        coalesce(sum(amount),0) amount_sum
   from payment_attempts
  where rental_id='${OID}';" | cat

docker compose exec -T db psql -U app -d rental -c \
"select coalesce(amount_total,0) debt
   from debts where rental_id='${OID}';" | cat

echo
echo "== status =="
http_get_json "$BASE/rentals/${OID}/status" | python3 -m json.tool

echo
echo "OK"
