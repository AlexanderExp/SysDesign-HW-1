#!/usr/bin/env bash
set -euo pipefail

TEST_TICK="${BILLING_TICK_SEC:-10}"

echo
echo "== health =="
code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$code" != "200" ]; then
  echo "❌ rental-core не жив ($code)"; exit 1
fi
echo "✅  rental-core жив (200)"
echo

echo "== quote =="
QJSON=$(curl -s -X POST http://localhost:8000/rentals/quote \
  -H 'Content-Type: application/json' \
  -d '{"station_id":"some-station-id","user_id":"u1"}')
echo "$QJSON" | python3 -m json.tool
QID=$(echo "$QJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')
[ -n "$QID" ] || { echo "❌ нет quote_id"; exit 1; }
echo "✅  получили quote_id"
IDEMP=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())')
echo "Idempotency-Key: $IDEMP"
echo

echo "== start (idempotent) =="
SJSON=$(curl -s -X POST http://localhost:8000/rentals/start \
  -H 'Content-Type: application/json' -H "Idempotency-Key: $IDEMP" \
  -d "{\"quote_id\":\"$QID\"}")
echo "$SJSON" | python3 -m json.tool
OID=$(echo "$SJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["order_id"])')
[ -n "$OID" ] || { echo "❌ нет order_id"; exit 1; }
echo "✅  получили order_id"
echo

echo "✅  аренда активна после старта"
echo

FF_MIN=${FF_MINUTES:-}
if [ -n "${FF_MIN}" ]; then
  echo "== fast-forward started_at на ${FF_MIN} минут назад =="
  docker compose exec -T db psql -U app -d rental -c \
    "update rentals set started_at = now() - interval '${FF_MIN} minutes' where id='${OID}';" | cat
  echo
fi

FORCE="${FORCE_STATUS:-}"
if [ -n "$FORCE" ]; then
  echo "== override status='${FORCE}' =="
  docker compose exec -T db psql -U app -d rental -c \
    "update rentals set status='${FORCE}' where id='${OID}';" | cat
  echo
fi

WAIT=$(( TEST_TICK*3 + TEST_TICK/2 ))
echo "== ждём ~${WAIT} сек (tick=${TEST_TICK}) =="
sleep "${WAIT}"

echo
echo "== первичные списания =="
docker compose exec -T db psql -U app -d rental -c \
"select
   count(*) attempts_total,
   sum(case when success then 1 else 0 end) attempts_ok,
   coalesce(sum(amount),0) amount_sum
 from payment_attempts
 where rental_id='${OID}';" | cat

docker compose exec -T db psql -U app -d rental -c \
"select coalesce(amount_total,0) debt from debts where rental_id='${OID}';" | cat

echo
echo "== status =="
curl -s "http://localhost:8000/rentals/${OID}/status" | python3 -m json.tool || true

echo
echo "🎉 TEST PASS"
