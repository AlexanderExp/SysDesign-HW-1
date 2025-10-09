#!/usr/bin/env bash
set -euo pipefail

API=${API:-http://localhost:8000}

# маленькие помощники
uuid() { command -v uuidgen >/dev/null && uuidgen || python3 -c 'import uuid; print(uuid.uuid4())'; }
http() { curl -sS -o "${2}" -w "%{http_code}" "$1"; } # usage: http <url_with_args> <out_file>

echo "== health =="
code=$(curl -s -o /dev/null -w "%{http_code}" "${API}/health")
echo "HTTP ${code}"
[ "$code" = "200" ] || { echo "FAIL /health"; exit 1; }

echo "== quote =="
resp_q=$(curl -s -X POST "${API}/rentals/quote" \
  -H 'Content-Type: application/json' \
  -d '{"station_id":"some-station-id","user_id":"u1"}')
echo "$resp_q" | python3 -m json.tool
QUOTE_ID=$(echo "$resp_q" | python3 -c 'import sys,json; print(json.load(sys.stdin)["quote_id"])')
[ -n "$QUOTE_ID" ] || { echo "FAIL: no quote_id"; exit 1; }

echo "== start (idempotent) =="
IDEMP=$(uuid); echo "Idempotency-Key: $IDEMP"
resp_s1=$(curl -s -X POST "${API}/rentals/start" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: ${IDEMP}" \
  -d "{\"quote_id\":\"${QUOTE_ID}\"}")
echo "$resp_s1" | python3 -m json.tool
ORDER_ID=$(echo "$resp_s1" | python3 -c 'import sys,json; print(json.load(sys.stdin)["order_id"])')
[ -n "$ORDER_ID" ] || { echo "FAIL: no order_id on first start"; exit 1; }

resp_s2=$(curl -s -X POST "${API}/rentals/start" \
  -H 'Content-Type: application/json' \
  -H "Idempotency-Key: ${IDEMP}" \
  -d "{\"quote_id\":\"${QUOTE_ID}\"}")
ORDER_ID2=$(echo "$resp_s2" | python3 -c 'import sys,json; print(json.load(sys.stdin)["order_id"])')
[ "$ORDER_ID" = "$ORDER_ID2" ] || { echo "FAIL: idempotency mismatch"; exit 1; }

echo "== status (must be active) =="
resp_st=$(curl -s "${API}/rentals/${ORDER_ID}/status")
echo "$resp_st" | python3 -m json.tool
status=$(echo "$resp_st" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')
[ "$status" = "active" ] || { echo "FAIL: status != active"; exit 1; }

echo "== stop (first call) =="
code=$(curl -s -o /tmp/stop1.json -w "%{http_code}" -X POST "${API}/rentals/${ORDER_ID}/stop" \
  -H 'Content-Type: application/json' \
  -d '{"station_id":"another-station"}')
echo "HTTP ${code}"
cat /tmp/stop1.json | python3 -m json.tool
[ "$code" = "200" ] || { echo "FAIL: stop1 code ${code}"; exit 1; }

echo "== stop (second call, idempotent) =="
code=$(curl -s -o /tmp/stop2.json -w "%{http_code}" -X POST "${API}/rentals/${ORDER_ID}/stop" \
  -H 'Content-Type: application/json' \
  -d '{"station_id":"another-station"}')
echo "HTTP ${code}"
cat /tmp/stop2.json | python3 -m json.tool
[ "$code" = "200" ] || { echo "FAIL: stop2 code ${code}"; exit 1; }

echo "✅ SMOKE PASS"
