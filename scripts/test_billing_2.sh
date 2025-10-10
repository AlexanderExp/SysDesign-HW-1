#!/usr/bin/env bash
set -euo pipefail

TEST_TICK="${BILLING_TICK_SEC:-10}"
FF_MIN="${FF_MINUTES:-}"
FORCE="${FORCE_STATUS:-}"

echo
echo "== health =="
code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
if [ "$code" != "200" ]; then echo "❌ rental-core не жив ($code)"; exit 1; fi
echo "✅  rental-core жив (200)"

echo
echo "== quote =="
QJSON=$(curl -s -X POST http://localhost:8000/rentals/quote \
  -H 'Content-Type: application/json' \
  -d '{"station_id":"some-station-id","user_id":"u1"}')
echo "$QJSON" | python3 -m json.tool
QID=$(echo "$QJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')
PPH=$(echo "$QJSON" | python3 -c 'import sys,json; print(int(json.load(sys.stdin)["price_per_hour"]))')
FREEMIN=$(echo "$QJSON" | python3 -c 'import sys,json; print(int(json.load(sys.stdin)["free_period_min"]))')
[ -n "$QID" ] || { echo "❌ нет quote_id"; exit 1; }
echo "✅  получили quote_id (pph=$PPH, free_min=$FREEMIN)"
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
echo "✅  получили order_id=$OID"

echo
if [ -n "${FF_MIN}" ]; then
  echo "== fast-forward started_at на ${FF_MIN} минут назад =="
  docker compose exec -T db psql -U app -d rental -c \
    "update rentals set started_at = now() - interval '${FF_MIN} minutes' where id='${OID}';" | cat
fi

if [ -n "$FORCE" ]; then
  echo
  echo "== override status='${FORCE}' =="
  docker compose exec -T db psql -U app -d rental -c \
    "update rentals set status='${FORCE}' where id='${OID}';" | cat
fi

WAIT=$(( TEST_TICK*3 + TEST_TICK/2 ))
echo
echo "== ждём ~${WAIT} сек (tick=${TEST_TICK}) =="
sleep "${WAIT}"

echo
echo "== первичные списания =="
# аккуратный CSV-вывод
IFS=',' read -r ATT_TOTAL ATT_OK AMOUNT_SUM <<<"$(
  docker compose exec -T db psql -U app -d rental -tA -F, -c \
  "select count(*),
          sum(case when success then 1 else 0 end),
          coalesce(sum(amount),0)
   from payment_attempts
   where rental_id='${OID}';"
)"
DEBT="$(docker compose exec -T db psql -U app -d rental -tA -c \
  "select coalesce((select amount_total from debts where rental_id='${OID}'),0);")"

printf "attempts_total=%s, attempts_ok=%s, amount_sum=%s, debt=%s\n" "$ATT_TOTAL" "$ATT_OK" "$AMOUNT_SUM" "$DEBT"

# считаем ожидаемую сумму
EXPECTED="$(python3 - <<PY
pph = int("$PPH")
ff  = int("${FF_MIN:-0}")
free = int("$FREEMIN")
m = max(0, ff - free)
hours = m // 60
rem   = m % 60
# почасово + округление вверх для остаточных минут
import math
expected = pph*hours + math.ceil(rem * pph / 60)
print(expected)
PY
)"

echo "expected_amount=$EXPECTED (pph=$PPH, ff=${FF_MIN:-0}, free=$FREEMIN)"

# проверяем инварианты
if [ "${ATT_OK:-0}" -lt 1 ]; then
  echo "❌ ожидали >=1 успешной попытки списания"; exit 1
fi
if [ "${AMOUNT_SUM:-0}" -ne "${EXPECTED:-0}" ]; then
  echo "❌ amount_sum=${AMOUNT_SUM} != expected=${EXPECTED}"; exit 1
fi
if [ "${DEBT:-0}" -ne 0 ]; then
  echo "❌ debt должен быть 0, сейчас ${DEBT}"; exit 1
fi

echo
echo "== status =="
STATUS_JSON=$(curl -s "http://localhost:8000/rentals/${OID}/status" | python3 -m json.tool)
echo "$STATUS_JSON"
TOTAL_AMOUNT=$(echo "$STATUS_JSON" | python3 -c 'import sys,json; print(int(json.load(sys.stdin)["total_amount"]))' 2>/dev/null || echo 0)
if [ "$TOTAL_AMOUNT" -ne "$EXPECTED" ]; then
  echo "❌ total_amount=${TOTAL_AMOUNT} != expected=${EXPECTED}"; exit 1
fi

echo
echo "🎉 TEST PASS"
