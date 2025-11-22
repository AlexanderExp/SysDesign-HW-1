#!/usr/bin/env bash
set -euo pipefail

# ========= настройки по умолчанию (можно переопределять через env) =========
RENTAL_CORE_BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
USER_ID="${USER_ID:-u1}"
STATION_ID="${STATION_ID:-some-station-id}"

TARIFF_TTL_SEC="${TARIFF_TTL_SEC:-45}"
CONFIG_REFRESH_SEC="${CONFIG_REFRESH_SEC:-20}"
BILLING_TICK_SEC="${BILLING_TICK_SEC:-10}"
R_BUYOUT="${R_BUYOUT:-5000}"

# поведение
SKIP_BRINGUP="${SKIP_BRINGUP:-0}"           # 1 — не поднимать стек (если он уже запущен)
SHOW_LOGS_ON_FAIL="${SHOW_LOGS_ON_FAIL:-0}"  # 1 — печатать логи сервисов, если какой-то тест упал

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; BLU='\033[0;34m'; NC='\033[0m'
fail() { echo -e "${RED}❌ $*${NC}"; }
ok()   { echo -e "${GRN}✅ $*${NC}"; }
note() { echo -e "${YLW}(note) $*${NC}"; }
hdr()  { echo -e "\n${BLU}== $* ==${NC}"; }

ensure_executable() {
  local f="$1"
  [ -x "$f" ] || chmod +x "$f"
}

wait_http_200() {
  local url="$1"; local tries="${2:-30}"
  local code
  for _ in $(seq 1 "$tries"); do
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)
    [ "$code" = "200" ] && return 0
    sleep 1
  done
  echo "$code"
  return 1
}

dump_logs() {
  echo
  echo "---- docker compose ps ----"
  docker compose ps || true
  echo
  echo "---- logs: external-stubs ----"
  docker compose logs --no-color --tail=300 external-stubs || true
  echo
  echo "---- logs: rental-core ----"
  docker compose logs --no-color --tail=300 rental-core || true
  echo
  echo "---- logs: billing-worker ----"
  docker compose logs --no-color --tail=300 billing-worker || true
}

run_test() {
  local name="$1"; shift
  local cmd="$*"
  hdr "$name"
  if eval "$cmd"; then
    ok "$name"
    return 0
  else
    fail "$name"
    [ "$SHOW_LOGS_ON_FAIL" = "1" ] && dump_logs
    return 1
  fi
}

# ========= подготовка =========
ensure_executable ./scripts/integration_cache_and_configs.sh
ensure_executable ./scripts/test_money_flows.sh
ensure_executable ./scripts/test_buyout_auto_finish.sh
ensure_executable ./scripts/test_idempotency_and_errors.sh

if [ "$SKIP_BRINGUP" != "1" ]; then
  hdr "bring up stack"
  docker compose up -d --build db redis external-stubs rental-core billing-worker
fi

hdr "health"
if ! wait_http_200 "$RENTAL_CORE_BASE/api/v1/health" 45 >/dev/null; then
  code=$(curl -s -o /dev/null -w "%{http_code}" "$RENTAL_CORE_BASE/api/v1/health" || true)
  fail "rental-core not alive ($code)"
  exit 1
fi
ok "rental-core alive (200)"

if ! curl -fsS http://localhost:3629/configs >/dev/null; then
  fail "external-stubs /configs not responding"
  exit 1
fi
ok "external-stubs responds on /configs"
note "TEST windows: TARIFF_TTL_SEC=${TARIFF_TTL_SEC}s, CONFIG_REFRESH_SEC=${CONFIG_REFRESH_SEC}s, BILLING_TICK_SEC=${BILLING_TICK_SEC}s, R_BUYOUT=${R_BUYOUT}"

# ========= запуск тестов =========
FAIL=0

run_test "tariff cache & configs" \
  "TARIFF_TTL_SEC=${TARIFF_TTL_SEC} CONFIG_REFRESH_SEC=${CONFIG_REFRESH_SEC} \
   RENTAL_CORE_BASE=${RENTAL_CORE_BASE} STATION_ID=${STATION_ID} USER_ID=${USER_ID} \
   ./scripts/integration_cache_and_configs.sh" || FAIL=1

run_test "money flow smoke" \
  "BILLING_TICK_SEC=${BILLING_TICK_SEC} \
   RENTAL_CORE_BASE=${RENTAL_CORE_BASE} STATION_ID=${STATION_ID} USER_ID=${USER_ID} \
   ./scripts/test_money_flows.sh" || FAIL=1

run_test "money flow serious (billing)" \
  "BILLING_TICK_SEC=${BILLING_TICK_SEC} FF_MINUTES=130 \
   RENTAL_CORE_BASE=${RENTAL_CORE_BASE} STATION_ID=${STATION_ID} USER_ID=${USER_ID} \
   ./scripts/test_billing_2.sh" || FAIL=1

run_test "buyout auto-finish" \
  "R_BUYOUT=${R_BUYOUT} BILLING_TICK_SEC=${BILLING_TICK_SEC} \
   RENTAL_CORE_BASE=${RENTAL_CORE_BASE} STATION_ID=${STATION_ID} USER_ID=${USER_ID} \
   ./scripts/test_buyout_auto_finish.sh" || FAIL=1

run_test "idempotency & errors" \
  "RENTAL_CORE_BASE=${RENTAL_CORE_BASE} STATION_ID=${STATION_ID} USER_ID=${USER_ID} \
   ./scripts/test_idempotency_and_errors.sh" || FAIL=1

# ========= сводка / exit code =========
hdr "summary"
if [ "$FAIL" -eq 0 ]; then
  ok "ALL TESTS PASSED"
  exit 0
else
  fail "SOME TESTS FAILED"
  exit 1
fi
