#!/usr/bin/env bash
set -euo pipefail

TTL="${TARIFF_TTL_SEC:-60}"

barrier_now() {
  # RFC3339 без Z — docker compose logs понимает
  TS="$(date -u +"%Y-%m-%dT%H:%M:%S")"
  # маленький зазор, чтобы логи после барьера точно попали в --since
  sleep 1
}

count_tariff_calls() {
  docker compose logs external-stubs --since "$TS" 2>/dev/null \
    | grep -c "GET /tariff" || true
}

quote_once() {
  curl -s -X POST http://localhost:8000/rentals/quote \
    -H 'Content-Type: application/json' \
    -d '{"station_id":"some-station-id","user_id":"u1"}' > /dev/null
}

echo "== tariff cache test (TTL=${TTL}s) =="


sleep $(( EFF_TTL + 5 ))
# Барьер логов
barrier_now
base=$(count_tariff_calls)

# Два quote подряд — ожидаем только 1 запрос /tariff
quote_once
quote_once

after_warm=$(count_tariff_calls)
delta1=$(( after_warm - base ))
echo "calls after warmup: +${delta1}"
if [ "$delta1" -ne 1 ]; then
  echo "❌ ожидали ровно 1 вызов /tariff (кэш прогрелся), а получили $delta1"
  exit 1
fi

# Ждём пока TTL истечёт
echo "sleep ${TTL}+2s to expire cache..."
sleep $(( TTL + 2 ))

# Ещё один quote — снова должен быть 1 вызов /tariff
quote_once
after_expire=$(count_tariff_calls)
delta2=$(( after_expire - after_warm ))
echo "calls after expire: +${delta2}"
if [ "$delta2" -ne 1 ]; then
  echo "❌ после истечения TTL ожидали 1 новый вызов /tariff, а получили $delta2"
  exit 1
fi

echo "✅ tariff cache behaves as expected"
