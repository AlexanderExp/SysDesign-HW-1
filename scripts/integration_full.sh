#!/usr/bin/env bash
set -euo pipefail

export RENTAL_CORE_BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
export STATION_ID="${STATION_ID:-some-station-id}"
export USER_ID="${USER_ID:-u1}"
export BILLING_TICK_SEC="${BILLING_TICK_SEC:-10}"
export R_BUYOUT="${R_BUYOUT:-5000}"
export TARIFF_TTL_SEC="${TARIFF_TTL_SEC:-45}"
export CONFIG_REFRESH_SEC="${CONFIG_REFRESH_SEC:-20}"

echo "== bring up stack =="
docker compose up -d db redis external-stubs rental-core billing-worker
sleep 2

FAIL=0

echo
echo "== tariff cache & configs =="
if ./scripts/integration_cache_and_configs.sh; then
  echo "OK cache+configs"
else FAIL=1; fi

echo
echo "== money flow =="
if ./scripts/test_money_flows.sh; then
  echo "OK money"
else FAIL=1; fi

echo
echo "== buyout auto-finish =="
if ./scripts/test_buyout_auto_finish.sh; then
  echo "OK buyout"
else FAIL=1; fi

echo
echo "== idempotency & errors =="
if ./scripts/test_idempotency_and_errors.sh; then
  echo "OK idem/errors"
else FAIL=1; fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "🎉 ALL INTEGRATION TESTS PASS"
else
  echo "❌ SOME TESTS FAILED"; exit 1
fi
