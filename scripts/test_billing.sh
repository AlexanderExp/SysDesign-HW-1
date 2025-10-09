#!/usr/bin/env bash
# scripts/test_billing.sh
set -Eeuo pipefail

# -------------------- ПАРАМЕТРЫ --------------------
# можно переопределять из окружения при запуске
BASE=${BASE:-http://localhost:8000}

DB_SVC=${DB_SVC:-db}
DB_NAME=${DB_NAME:-rental}
DB_USER=${DB_USER:-app}

# период тика воркера (НУЖЕН для ожидания в тесте; сам воркер настраивается через .env/docker-compose)
TICK=${BILLING_TICK_SEC:-30}
# ждём с запасом 3 тика
WAIT=$(( TICK*3 + 3 ))

# «ускорение времени»: на сколько минут отмотать started_at назад
FF_MINUTES=${FF_MINUTES:-0}

# Принудительная установка статуса заказа (например, ACTIVE)
FORCE_STATUS=${FORCE_STATUS:-}

# Если включить, скрипт попытается сам поднять billing-worker (не обязателен)
ENSURE_WORKER=${ENSURE_WORKER:-1}

# -------------------- УТИЛИТЫ --------------------
banner() { echo; echo "== $* =="; }

json_get() { python3 -c '
import sys, json
path = sys.argv[1]
obj = json.load(sys.stdin)
for k in path.split("."):
    obj = obj[k]
print(obj)
' "$1"; }

sql() { docker compose exec -T "$DB_SVC" psql -U "$DB_USER" -d "$DB_NAME" -Atc "$1"; }

assert() {
  if ! eval "$1"; then
    echo "❌  $2"
    exit 1
  else
    echo "✅  $2"
  fi
}

on_fail_dump() {
  echo
  echo "---- diagnostics (last 60s worker logs) ----"
  docker compose logs --since=60s billing-worker || true
  echo "-------------------------------------------"
}
trap on_fail_dump ERR

ensure_worker() {
  if [[ "$ENSURE_WORKER" != "1" ]]; then
    return 0
  fi
  # запущен ли контейнер?
  if ! docker compose ps --status running billing-worker >/dev/null 2>&1; then
    echo "(ensure) запускаю billing-worker…"
    docker compose up -d billing-worker
    sleep 2
  fi
  # покажем последний лог про тик (если есть)
  local tl
  tl=$(docker compose logs --since 5s billing-worker 2>/dev/null | grep -E "\[billing-worker\] tick=" | tail -1 || true)
  if [[ -n "$tl" ]]; then
    echo "(ensure) $tl"
  else
    echo "(ensure) не удалось прочитать тик воркера из логов (нормально). TEST_TICK=${TICK}s"
  fi
}

# -------------------- СТАРТ --------------------
ensure_worker

banner "health"
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/health")
assert "[[ $code -eq 200 ]]" "rental-core жив ($code)"

banner "quote"
QUOTE_JSON=$(
  curl -s -X POST "$BASE/rentals/quote" \
    -H 'Content-Type: application/json' \
    -d '{"station_id":"some-station-id","user_id":"u1"}'
)
echo "$QUOTE_JSON" | python3 -m json.tool

Q=$(echo "$QUOTE_JSON" | json_get quote_id)
assert "[[ -n \"$Q\" ]]" "получили quote_id"

IDEMP=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())')
echo "Idempotency-Key: $IDEMP"

banner "start (idempotent)"
START_JSON=$(
  curl -s -X POST "$BASE/rentals/start" \
    -H 'Content-Type: application/json' \
    -H "Idempotency-Key: $IDEMP" \
    -d "{\"quote_id\":\"$Q\"}"
)
echo "$START_JSON" | python3 -m json.tool

OID=$(echo "$START_JSON" | json_get order_id)
STATUS=$(echo "$START_JSON" | json_get status)

assert "[[ -n \"$OID\" ]]" "получили order_id"
assert "[[ \"$STATUS\" == active ]]" "аренда активна после старта"

# -------------------- ДОП. МОДИФИКАЦИИ ДЛЯ ТЕСТА --------------------
if [[ "$FF_MINUTES" -gt 0 ]]; then
  banner "fast-forward started_at на ${FF_MINUTES} минут назад"
  sql "update rentals set started_at = now() - interval '${FF_MINUTES} minutes' where id='${OID}';"
fi

if [[ -n "$FORCE_STATUS" ]]; then
  banner "override status='${FORCE_STATUS}'"
  sql "update rentals set status='${FORCE_STATUS}' where id='${OID}';"
fi

banner "ждём ~${WAIT} сек (tick=${TICK})"
sleep "$WAIT"

# -------------------- ПРОВЕРКА СПИСАНИЙ --------------------
banner "первичные списания"
PA_CNT=$(sql "select count(*) from payment_attempts where rental_id='${OID}';")
PA_OK=$(sql "select coalesce(sum(case when success then 1 else 0 end),0) from payment_attempts where rental_id='${OID}';")
PA_SUM=$(sql "select coalesce(sum(amount),0) from payment_attempts where rental_id='${OID}';")
DEBT=$(sql "select coalesce((select amount_total from debts where rental_id='${OID}'),0);")

echo "attempts_total=$PA_CNT, attempts_ok=$PA_OK, amount_sum=$PA_SUM, debt=$DEBT"
assert "[[ $PA_CNT -ge 1 ]]" "воркер сделал >=1 попытки списания"

# финальный снимок статуса
banner "status"
curl -s "$BASE/rentals/$OID/status" | python3 -m json.tool

echo
echo "🎉 TEST PASS"
