#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$DIR/lib_http.sh"

BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
USER_ID="${USER_ID:-u1}"
STATION_ID="${STATION_ID:-some-station-id}"

# Должно совпадать с тем, что у billing-worker в env
TICK="${BILLING_TICK_SEC:-2}"

# Порог для buyout — ТОЛЬКО для проверок в тесте;
# у billing-worker он тоже должен быть таким же при старте.
R_BUYOUT="${R_BUYOUT:-50}"

# Каждый шаг добавляет по STEP_MINUTES минут аренды
STEP_MINUTES="${STEP_MINUTES:-10}"
# Количество шагов (5 шагов по 10 минут = 50 минут)
STEPS="${STEPS:-5}"

# Имя сервиса с внешними заглушками в docker compose
EXTERNAL_SERVICE_NAME="${EXTERNAL_SERVICE_NAME:-external-stubs}"

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
echo "== подготовка: гасим платежный сервис, чтобы все списания падали в долг =="
echo "Останавливаем контейнер ${EXTERNAL_SERVICE_NAME} ..."
docker compose stop "${EXTERNAL_SERVICE_NAME}" >/dev/null

# На всякий случай поднимаем его обратно в конце теста
cleanup() {
  echo
  echo "== cleanup: поднимаем ${EXTERNAL_SERVICE_NAME} обратно =="
  docker compose start "${EXTERNAL_SERVICE_NAME}" >/dev/null || true
}
trap cleanup EXIT

echo
echo "== демо: регулярные неуспешные списания до buyout =="
echo "TICK=${TICK}s, STEP_MINUTES=${STEP_MINUTES}, STEPS=${STEPS}, R_BUYOUT=${R_BUYOUT}"
echo "Будем прокручивать started_at назад и смотреть рост долга и попыток списания."

step=1
BUYOUT_SEEN=0

while [ "$step" -le "$STEPS" ]; do
  ff_min=$(( STEP_MINUTES * step ))
  echo
  echo "---- Шаг ${step}/${STEPS}: эмулируем длительность аренды ~${ff_min} минут ----"

  # Сдвигаем started_at назад на ff_min минут, статус оставляем ACTIVE
  docker compose exec -T db psql -U app -d rental -c \
    "update rentals set started_at = now() - interval '${ff_min} minutes', status='ACTIVE' where id='${OID}';" | cat

  # Ждём чуть больше одного тика, чтобы billing-worker успел среагировать
  WAIT=$(( TICK + 1 ))
  echo
  echo "Ждём ~${WAIT} сек, чтобы сработал биллинг (tick=${TICK}) ..."
  sleep "$WAIT"

  echo
  echo "== Состояние после шага ${step} =="

  # payment_attempts (все должны быть success=false, так как платежка недоступна)
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
  printf "Итого попыток: %s, успешных: %s, суммарно попытались списать: %s, долг: %s\n" \
    "$ATT_TOTAL" "$ATT_OK" "$AMOUNT_SUM" "$DEBT"

  # Статус заказа через API
  echo
  echo "-- /rentals/${OID}/status:"
  STAT=$(http_get_json "$BASE/rentals/${OID}/status")
  echo "$STAT" | python3 -m json.tool
  STATUS=$(echo "$STAT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')

  if [ "$STATUS" = "BUYOUT" ] || [ "$STATUS" = "FINISHED" ]; then
    echo
    echo "Статус уже $STATUS — выходим из цикла."
    BUYOUT_SEEN=1
    break
  fi

  step=$(( step + 1 ))
done

echo
echo "== финальная проверка =="

# Итоговая статистика по попыткам и долгу
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

STAT=$(http_get_json "$BASE/rentals/${OID}/status")
STATUS=$(echo "$STAT" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')

echo "attempts_total=$ATT_TOTAL, attempts_ok=$ATT_OK, amount_sum=$AMOUNT_SUM, debt=$DEBT, status=$STATUS"

# 1) Должны быть хотя бы 2 попытки списания
if [ "${ATT_TOTAL:-0}" -lt 2 ]; then
  echo "❌ ожидали хотя бы 2 попытки списания"
  exit 1
fi

# 2) Все попытки должны быть неуспешными (платёжка лежит)
if [ "${ATT_OK:-0}" -ne 0 ]; then
  echo "❌ ожидали 0 успешных попыток списания, но есть ${ATT_OK}"
  exit 1
fi

# 3) Долг должен быть > 0
if [ "${DEBT:-0}" -le 0 ]; then
  echo "❌ долг должен быть > 0"
  exit 1
fi

# 4) Если R_BUYOUT маленький и шагов достаточно — должны увидеть BUYOUT
if [ "$DEBT" -ge "$R_BUYOUT" ] && [ "$STATUS" != "BUYOUT" ] && [ "$STATUS" != "FINISHED" ]; then
  echo "❌ при долге >= R_BUYOUT ожидаем статус BUYOUT/FINISHED, а сейчас $STATUS"
  exit 1
fi

echo
echo "🎉 BUYOUT + DEBT TEST PASS"
