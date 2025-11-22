#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib_http.sh"

BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
USER_ID="${USER_ID:-u1}"
STATION_ID="${STATION_ID:-some-station-id}"

TICK="${BILLING_TICK_SEC:-2}"
STEP_MINUTES="${STEP_MINUTES:-10}"

SUCCESS_STEPS="${SUCCESS_STEPS:-2}"   # сколько шагов делаем с живой платёжкой
FAIL_STEPS="${FAIL_STEPS:-3}"         # сколько шагов делаем с мёртвой платёжкой
R_BUYOUT="${R_BUYOUT:-50}"

EXTERNAL_SERVICE_NAME="${EXTERNAL_SERVICE_NAME:-external-stubs}"

echo
echo "== health =="
http_get_json "$BASE/api/v1/health" >/dev/null
echo "✅ rental-core alive"

echo
echo "== start rental =="
QJSON=$(http_post_json "$BASE/api/v1/rentals/quote" \
  "{\"station_id\":\"$STATION_ID\",\"user_id\":\"$USER_ID\"}")
echo "$QJSON" | python3 -m json.tool

QID=$(echo "$QJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')
PPH=$(echo "$QJSON" | python3 -c 'import sys,json; print(int(json.load(sys.stdin)["price_per_hour"]))')
FREEMIN=$(echo "$QJSON" | python3 -c 'import sys,json; print(int(json.load(sys.stdin)["free_period_min"]))')
echo "quote_id=$QID (pph=$PPH, free_min=$FREEMIN)"

IDEMP=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())')

SJSON=$(http_post_json "$BASE/api/v1/rentals/start" \
  "{\"quote_id\":\"$QID\"}" \
  "Idempotency-Key: $IDEMP")
echo "$SJSON" | python3 -m json.tool

OID=$(echo "$SJSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["order_id"])')
echo "order_id=$OID"

cleanup() {
  echo
  echo "== cleanup: поднимаем ${EXTERNAL_SERVICE_NAME} обратно =="
  docker compose start "${EXTERNAL_SERVICE_NAME}" >/dev/null || true
}
trap cleanup EXIT

echo
echo "== demo: часть paid, часть debt, потом BUYOUT (paid+debt) =="
echo "TICK=${TICK}s, STEP_MINUTES=${STEP_MINUTES}, SUCCESS_STEPS=${SUCCESS_STEPS}, FAIL_STEPS=${FAIL_STEPS}, R_BUYOUT=${R_BUYOUT}"

step=1
TOTAL_STEPS=$(( SUCCESS_STEPS + FAIL_STEPS ))

BUYOUT_HAPPENED=0
BUYOUT_ATTEMPTS=0
BUYOUT_PAID=0
BUYOUT_DEBT=0

# --- 1) Шаги с живой платёжкой (успешные списания) ---
while [ "$step" -le "$SUCCESS_STEPS" ]; do
  ff_min=$(( STEP_MINUTES * step ))
  echo
  echo "---- Шаг ${step}/${TOTAL_STEPS}: платёжка ЖИВА, эмулируем ~${ff_min} минут ----"

  docker compose exec -T db psql -U app -d rental -c \
    "update rentals set started_at = now() - interval '${ff_min} minutes' where id='${OID}' and status='ACTIVE';" | cat

  WAIT=$(( TICK + 1 ))
  echo
  echo "Ждём ~${WAIT} сек (tick=${TICK}) ..."
  sleep "$WAIT"

  echo
  echo "== Состояние после шага ${step} =="

  echo "-- payment_attempts:"
  docker compose exec -T db psql -U app -d rental -c \
    "select id, amount, success, created_at
     from payment_attempts
     where rental_id='${OID}'
     order by id;" | cat

  # сводка: всего попыток, успешных, общая сумма
  IFS=',' read -r ATT_TOTAL ATT_OK AMOUNT_SUM <<<"$(
    docker compose exec -T db psql -U app -d rental -tA -F, -c \
      "select count(*),
              coalesce(sum(case when success then 1 else 0 end),0),
              coalesce(sum(amount),0)
       from payment_attempts
       where rental_id='${OID}';"
  )"

  DEBT=$(docker compose exec -T db psql -U app -d rental -tA -c \
    "select coalesce((select amount_total from debts where rental_id='${OID}'),0);")

  echo
  printf "Итого попыток: %s, успешных: %s, суммарно попытались списать: %s, долг: %s\n" \
    "$ATT_TOTAL" "$ATT_OK" "$AMOUNT_SUM" "$DEBT"

  echo
  echo "-- /api/v1/rentals/${OID}/status:"
  STAT=$(http_get_json "$BASE/api/v1/rentals/${OID}/status")
  echo "$STAT" | python3 -m json.tool
  STATUS=$(echo "$STAT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')

  if [ "$STATUS" = "BUYOUT" ] || [ "$STATUS" = "FINISHED" ]; then
    echo "⚠️ ранний BUYOUT уже на успешных списаниях, дальше тест смешения paid/debt не имеет смысла"
    BUYOUT_HAPPENED=1

    BUYOUT_PAID=$(docker compose exec -T db psql -U app -d rental -tA -c \
      "select coalesce(sum(amount),0)
       from payment_attempts
       where rental_id='${OID}' and success;")

    BUYOUT_DEBT=$(docker compose exec -T db psql -U app -d rental -tA -c \
      "select coalesce((select amount_total from debts where rental_id='${OID}'),0);")

    BUYOUT_ATTEMPTS="$ATT_TOTAL"
    break
  fi

  step=$(( step + 1 ))
done

if [ "$BUYOUT_HAPPENED" -eq 0 ]; then
  echo
  echo "== выключаем платёжный сервис: дальше все попытки должны уходить в долг =="
  docker compose stop "${EXTERNAL_SERVICE_NAME}" >/dev/null
fi

# --- 2) Шаги с мёртвой платёжкой (долг) ---
while [ "$BUYOUT_HAPPENED" -eq 0 ] && [ "$step" -le "$TOTAL_STEPS" ]; do
  ff_min=$(( STEP_MINUTES * step ))
  echo
  echo "---- Шаг ${step}/${TOTAL_STEPS}: платёжка заглушена, эмулируем ~${ff_min} минут ----"

  docker compose exec -T db psql -U app -d rental -c \
    "update rentals set started_at = now() - interval '${ff_min} minutes' where id='${OID}' and status='ACTIVE';" | cat

  WAIT=$(( TICK + 1 ))
  echo
  echo "Ждём ~${WAIT} сек (tick=${TICK}) ..."
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

  DEBT=$(docker compose exec -T db psql -U app -d rental -tA -c \
    "select coalesce((select amount_total from debts where rental_id='${OID}'),0);")

  echo
  printf "Итого попыток: %s, успешных: %s, суммарно попытались списать: %s, долг: %s\n" \
    "$ATT_TOTAL" "$ATT_OK" "$AMOUNT_SUM" "$DEBT"

  echo
  echo "-- /api/v1/rentals/${OID}/status:"
  STAT=$(http_get_json "$BASE/api/v1/rentals/${OID}/status")
  echo "$STAT" | python3 -m json.tool
  STATUS=$(echo "$STAT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')

  if [ "$STATUS" = "BUYOUT" ] || [ "$STATUS" = "FINISHED" ]; then
    echo
    echo "Статус уже $STATUS — фиксируем момент BUYOUT и выходим."

    BUYOUT_HAPPENED=1
    BUYOUT_ATTEMPTS="$ATT_TOTAL"

    BUYOUT_PAID=$(docker compose exec -T db psql -U app -d rental -tA -c \
      "select coalesce(sum(amount),0)
       from payment_attempts
       where rental_id='${OID}' and success;")

    BUYOUT_DEBT=$(docker compose exec -T db psql -U app -d rental -tA -c \
      "select coalesce((select amount_total from debts where rental_id='${OID}'),0);")

    break
  fi

  step=$(( step + 1 ))
done

if [ "$BUYOUT_HAPPENED" -eq 0 ]; then
  echo "❌ аренда не перешла в BUYOUT за ${TOTAL_STEPS} шагов"
  exit 1
fi

echo
echo "== финальная проверка (должны быть и paid, и debt) =="

# Проверяем, что есть хотя бы одна успешная попытка (paid > 0)
if [ "$BUYOUT_PAID" -le 0 ]; then
  echo "❌ ожидали хотя бы одну успешную попытку списания (часть должна быть оплачена)"
  exit 1
fi

# Долг должен быть > 0
if [ "$BUYOUT_DEBT" -le 0 ]; then
  echo "❌ ожидали положительный долг в момент BUYOUT в этом тесте"
  exit 1
fi

SUM_TOTAL=$(( BUYOUT_PAID + BUYOUT_DEBT ))
echo "paid=${BUYOUT_PAID}, debt=${BUYOUT_DEBT}, paid+debt=${SUM_TOTAL}"

if [ "$SUM_TOTAL" -lt "$R_BUYOUT" ]; then
  echo "⚠️ warning: paid+debt=${SUM_TOTAL} < R_BUYOUT=${R_BUYOUT} (проверь конфиг/тарифы/FF_MINUTES вручную)"
fi

echo
echo "== после BUYOUT ждём ещё пару тиков и убеждаемся, что ничего не меняется =="

sleep $(( TICK * 2 ))

# ещё раз собираем статистику
RES2=$(docker compose exec -T db psql -U app -d rental -tA -F, -c \
  "select count(*),
          coalesce(sum(case when success then 1 else 0 end),0),
          coalesce(sum(amount),0)
   from payment_attempts
   where rental_id='${OID}';")
IFS=',' read -r ATT_TOTAL2 ATT_OK2 AMOUNT_SUM2 <<<"$RES2"

DEBT2=$(docker compose exec -T db psql -U app -d rental -tA -c \
  "select coalesce((select amount_total from debts where rental_id='${OID}'),0);")

PAID2=$(docker compose exec -T db psql -U app -d rental -tA -c \
  "select coalesce(sum(amount),0)
   from payment_attempts
   where rental_id='${OID}' and success;")

STAT2=$(http_get_json "$BASE/api/v1/rentals/${OID}/status")
STATUS2=$(echo "$STAT2" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')

echo
echo "после ожидания: attempts_total=$ATT_TOTAL2, attempts_ok=$ATT_OK2, amount_sum=$AMOUNT_SUM2, paid=${PAID2}, debt=$DEBT2, status=$STATUS2"

if [ "$PAID2" -ne "$BUYOUT_PAID" ] || [ "$DEBT2" -ne "$BUYOUT_DEBT" ]; then
  echo "❌ после BUYOUT не должно меняться paid или debt"
  exit 1
fi

if [ "$STATUS2" != "BUYOUT" ] && [ "$STATUS2" != "FINISHED" ]; then
  echo "❌ после BUYOUT ожидаем статус BUYOUT/FINISHED, сейчас $STATUS2"
  exit 1
fi

echo
echo "🎉 TEST BUYOUT MIXED PAID+DEBT PASS"
