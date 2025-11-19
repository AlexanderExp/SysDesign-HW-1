#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib_http.sh"

BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
USER_ID="${USER_ID:-u1}"
STATION_ID="${STATION_ID:-some-station-id}"

TICK="${BILLING_TICK_SEC:-2}"          # должен совпадать с env у billing-worker
STEP_MINUTES="${STEP_MINUTES:-10}"     # сколько минут "добавляем" за шаг
MAX_STEPS="${MAX_STEPS:-6}"            # максимум шагов до BUYOUT
R_BUYOUT="${R_BUYOUT:-30}"             # ожидаемый порог выкупа (для проверок)

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
echo "== demo: successful charges -> BUYOUT -> no more charges =="
echo "TICK=${TICK}s, STEP_MINUTES=${STEP_MINUTES}, MAX_STEPS=${MAX_STEPS}, R_BUYOUT=${R_BUYOUT}"
echo "external-stubs НЕ трогаем, все списания должны быть успешными."

BUYOUT_ATTEMPTS=""
BUYOUT_AMOUNT=""
BUYOUT_DEBT=""

step=1
while [ "$step" -le "$MAX_STEPS" ]; do
  ff_min=$(( STEP_MINUTES * step ))
  echo
  echo "---- Шаг ${step}/${MAX_STEPS}: эмулируем длительность аренды ~${ff_min} минут ----"

  # Меняем started_at только если аренда ещё ACTIVE, статус не трогаем
  docker compose exec -T db psql -U app -d rental -c \
    "update rentals set started_at = now() - interval '${ff_min} minutes' where id='${OID}' and status='ACTIVE';" | cat

  WAIT=$(( TICK + 1 ))
  echo
  echo "Ждём ~${WAIT} сек, чтобы сработал биллинг (tick=${TICK}) ..."
  sleep "$WAIT"

  echo
  echo "== Состояние после шага ${step} =="

  echo "-- payment_attempts:"
  docker compose exec -T db psql -U app -d rental -c \
    "select id, amount, success, created_at
     from payment_attempts
     where rental_id='${OID}'
     order by id;" | cat

  IFS=',' read -r ATT_TOTAL ATT_OK AMOUNT_SUM <<<"$(
    docker compose exec -T db psql -U app -d rental -tA -F, -c \
      "select count(*),
              coalesce(sum(case when success then 1 else 0 end),0),
              coalesce(sum(amount),0)
       from payment_attempts
       where rental_id='${OID}';"
  )"

  DEBT="$(docker compose exec -T db psql -U app -d rental -tA -c \
    "select coalesce((select amount_total from debts where rental_id='${OID}'),0);")"

  echo
  printf "Итого попыток: %s, успешных: %s, суммарно списано: %s, долг: %s\n" \
    "$ATT_TOTAL" "$ATT_OK" "$AMOUNT_SUM" "$DEBT"

  echo
  echo "-- /rentals/${OID}/status:"
  STAT=$(http_get_json "$BASE/rentals/${OID}/status")
  echo "$STAT" | python3 -m json.tool
  STATUS=$(echo "$STAT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')

  if [ "$STATUS" = "BUYOUT" ] || [ "$STATUS" = "FINISHED" ]; then
    echo
    echo "Статус уже $STATUS — фиксим момент BUYOUT и выходим из цикла."
    BUYOUT_ATTEMPTS="$ATT_TOTAL"
    BUYOUT_AMOUNT="$AMOUNT_SUM"
    BUYOUT_DEBT="$DEBT"
    break
  fi

  step=$(( step + 1 ))
done

if [ -z "${BUYOUT_ATTEMPTS}" ]; then
  echo "❌ аренда не перешла в BUYOUT за ${MAX_STEPS} шагов"
  exit 1
fi

echo
echo "== проверяем инварианты в момент BUYOUT =="

if [ "${ATT_OK:-0}" -lt 1 ]; then
  echo "❌ ожидали хотя бы одну успешную попытку списания"
  exit 1
fi

if [ "${BUYOUT_DEBT:-0}" -ne 0 ]; then
  echo "❌ в этом тесте долг должен быть 0 в момент BUYOUT, сейчас ${BUYOUT_DEBT}"
  exit 1
fi

# Можно дополнительно проверить, что paid >= R_BUYOUT (если знаем тарифы/порог)
if [ "$BUYOUT_AMOUNT" -lt "$R_BUYOUT" ]; then
  echo "⚠️ warning: BUYOUT_AMOUNT=${BUYOUT_AMOUNT} < R_BUYOUT=${R_BUYOUT} (проверь конфиг/тарифы вручную)"
fi

echo
echo "== после BUYOUT ждём ещё пару тиков и убеждаемся, что ничего не меняется =="

sleep $(( TICK * 2 ))

IFS=',' read -r ATT_TOTAL2 ATT_OK2 AMOUNT_SUM2 <<<"$(
  docker compose exec -T db psql -U app -d rental -tA -F, -c \
    "select count(*),
            coalesce(sum(case when success then 1 else 0 end),0),
            coalesce(sum(amount),0)
     from payment_attempts
     where rental_id='${OID}';"
)"
DEBT2="$(docker compose exec -T db psql -U app -d rental -tA -c \
  "select coalesce((select amount_total from debts where rental_id='${OID}'),0);")"

STAT2=$(http_get_json "$BASE/rentals/${OID}/status")
STATUS2=$(echo "$STAT2" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')

echo
echo "после ожидания: attempts_total=$ATT_TOTAL2, attempts_ok=$ATT_OK2, amount_sum=$AMOUNT_SUM2, debt=$DEBT2, status=$STATUS2"

if [ "$ATT_TOTAL2" -ne "$BUYOUT_ATTEMPTS" ] || [ "$AMOUNT_SUM2" -ne "$BUYOUT_AMOUNT" ]; then
  echo "❌ после BUYOUT не должно появляться новых попыток/сумм списаний"
  exit 1
fi

if [ "$STATUS2" != "BUYOUT" ] && [ "$STATUS2" != "FINISHED" ]; then
  echo "❌ после BUYOUT ожидаем статус BUYOUT/FINISHED, сейчас $STATUS2"
  exit 1
fi

echo
echo "🎉 TEST BUYOUT PAID ONLY PASS"
