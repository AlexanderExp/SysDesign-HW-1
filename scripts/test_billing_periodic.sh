#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib_http.sh"

BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
USER_ID="${USER_ID:-u1}"
STATION_ID="${STATION_ID:-some-station-id}"

# шаг биллинга (сек), должен совпадать с тем, что у billing-worker
TICK="${BILLING_TICK_SEC:-5}"

# сколько минут добавляем каждый шаг
STEP_MINUTES="${STEP_MINUTES:-10}"

# количество шагов (3 шага = 10,20,30 минут)
STEPS="${STEPS:-3}"

echo
echo "== health =="
http_get_json "$BASE/health" >/dev/null
echo "✅ rental-core alive"

echo
echo "== start rental =="
QJSON=$(http_post_json "$BASE/rentals/quote" \
  "{\"station_id\":\"$STATION_ID\",\"user_id\":\"$USER_ID\"}")
echo "$QJSON" | python3 -m json.tool

QID=$(echo "$QJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')
PPH=$(echo "$QJSON" | python3 -c 'import sys,json; print(int(json.load(sys.stdin)["price_per_hour"]))')
FREEMIN=$(echo "$QJSON" | python3 -c 'import sys,json; print(int(json.load(sys.stdin)["free_period_min"]))')

echo "quote_id=$QID (pph=$PPH, free_min=$FREEMIN)"

IDEMP=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())')

SJSON=$(http_post_json "$BASE/rentals/start" \
  "{\"quote_id\":\"$QID\"}" \
  "Idempotency-Key: $IDEMP")
echo "$SJSON" | python3 -m json.tool

OID=$(echo "$SJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["order_id"])')
echo "order_id=$OID"

echo
echo "== periodic billing demo =="
echo "TICK=${TICK}s, STEP_MINUTES=${STEP_MINUTES}, STEPS=${STEPS}"
echo "Будем прокручивать started_at назад и смотреть, как растут списания."

step=1
while [ "$step" -le "$STEPS" ]; do
  ff_min=$(( STEP_MINUTES * step ))
  echo
  echo "---- Шаг ${step}/${STEPS}: эмулируем длительность аренды ~${ff_min} минут ----"

  # Сдвигаем started_at назад на ff_min минут
  docker compose exec -T db psql -U app -d rental -c \
    "update rentals set started_at = now() - interval '${ff_min} minutes', status='ACTIVE' where id='${OID}';" | cat

  # Ждём чуть больше одного тика, чтобы billing-worker успел среагировать
  WAIT=$(( TICK + 1 ))
  echo
  echo "Ждём ~${WAIT} сек, чтобы сработал биллинг (tick=${TICK}) ..."
  sleep "$WAIT"

  echo
  echo "== Состояние после шага ${step} =="

  # Печатаем попытки списаний
  echo "-- payment_attempts:"
  docker compose exec -T db psql -U app -d rental -c \
    "select id, amount, success, created_at
     from payment_attempts
     where rental_id='${OID}'
     order by id;" | cat

  # Сводка по попыткам
  IFS=',' read -r ATT_TOTAL ATT_OK AMOUNT_SUM <<<"$(
    docker compose exec -T db psql -U app -d rental -tA -F, -c \
      "select count(*),
              coalesce(sum(case when success then 1 else 0 end),0),
              coalesce(sum(amount),0)
       from payment_attempts
       where rental_id='${OID}';"
  )"

  # Текущий долг
  DEBT="$(docker compose exec -T db psql -U app -d rental -tA -c \
    "select coalesce((select amount_total from debts where rental_id='${OID}'),0);")"

  echo
  printf "Итого попыток: %s, успешных: %s, суммарно списано: %s, долг: %s\n" \
    "$ATT_TOTAL" "$ATT_OK" "$AMOUNT_SUM" "$DEBT"

  # Текущий статус заказа через API
  echo
  echo "-- /rentals/${OID}/status:"
  STAT=$(http_get_json "$BASE/rentals/${OID}/status")
  echo "$STAT" | python3 -m json.tool

  step=$(( step + 1 ))
done

echo
echo "== финальная проверка =="

# Итоговая статистика
IFS=',' read -r ATT_TOTAL ATT_OK AMOUNT_SUM <<<"$(
  docker compose exec -T db psql -U app -d rental -tA -F, -c \
    "select count(*),
            coalesce(sum(case when success then 1 else 0 end),0),
            coalesce(sum(amount),0)
     from payment_attempts
     where rental_id='${OID}';"
)"

echo "attempts_total=$ATT_TOTAL, attempts_ok=$ATT_OK, amount_sum=$AMOUNT_SUM"

# Ожидаем хотя бы STEPS успешных попыток и ненуловую сумму
if [ "${ATT_OK:-0}" -lt "$STEPS" ]; then
  echo "❌ ожидали хотя бы ${STEPS} успешных попыток списания"
  exit 1
fi

if [ "${AMOUNT_SUM:-0}" -le 0 ]; then
  echo "❌ суммарная списанная сумма должна быть > 0"
  exit 1
fi

echo
echo "🎉 PERIODIC BILLING TEST PASS"
