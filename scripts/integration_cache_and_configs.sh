#!/usr/bin/env bash
set -euo pipefail

RC_BASE="${RENTAL_CORE_BASE:-http://localhost:8000}"
STATION_ID="${STATION_ID:-some-station-id}"
USER_ID="${USER_ID:-u1}"

banner(){ echo; echo "== $* =="; }
ok(){ echo "✅ $*"; }
fail(){ echo "❌ $*"; }
note(){ echo "(note) $*"; }

wait_http_200() {
  local url="$1" max="${2:-30}" i=0
  while true; do
    if code="$(curl -s -o /dev/null -w '%{http_code}' "$url")" && [ "$code" = "200" ]; then return 0; fi
    i=$((i+1)); [ "$i" -ge "$max" ] && return 1
    sleep 1
  done
}

barrier_now(){ TS="$(date -u +"%Y-%m-%dT%H:%M:%S")"; sleep 1; }
count_in_ext_logs(){ docker compose logs external-stubs --since "$TS" 2>/dev/null | grep -a -cE "$1" || true; }
quote_once(){
  curl -s -X POST "$RC_BASE/api/v1/rentals/quote" -H 'Content-Type: application/json' \
    -d "{\"station_id\":\"$STATION_ID\",\"user_id\":\"$USER_ID\"}" >/dev/null
}

# --- bring up ---
banner "bring up stack"
docker compose up -d external-stubs db-rental db-billing rental-core >/dev/null
ok "docker services are up (requested)"

# --- health ---
banner "health"
wait_http_200 "$RC_BASE/api/v1/health" 40 && ok "rental-core alive (200)" || { fail "rental-core not healthy"; exit 1; }
wait_http_200 "http://localhost:3629/configs" 20 && ok "external-stubs responds on /configs" || { fail "external-stubs /configs"; exit 1; }

# --- determine effective TTL/refresh from container ---
EFF_TTL="$(docker compose exec -T rental-core sh -lc 'printf "%s" "${TARIFF_TTL_SEC:-}"' || true)"
[ -z "${EFF_TTL}" ] && EFF_TTL=60
EFF_CFG="$(docker compose exec -T rental-core sh -lc 'printf "%s" "${CONFIG_REFRESH_SEC:-}"' || true)"
[ -z "${EFF_CFG}" ] && EFF_CFG=30
note "effective TTL(TARIFF_TTL_SEC)=${EFF_TTL}s; config refresh=${EFF_CFG}s"

# --- tariff cache test ---
banner "tariff cache test (LRU+TTL)"
barrier_now
base_tariff_calls="$(count_in_ext_logs 'GET /tariff')"

# прогрев
quote_once; quote_once
after_warm="$(count_in_ext_logs 'GET /tariff')"
delta1=$(( after_warm - base_tariff_calls ))
echo "calls after warmup: +${delta1}"
if [ "$delta1" -ne 1 ]; then
  fail "ожидали 1 вызов /tariff при прогреве, получили ${delta1}"
  TAR_CACHE_PASS=0
else
  ok "кэш прогрелся: 1 GET /tariff"
  TAR_CACHE_PASS=1
fi

# ждём истечения фактического TTL и триггерим новый quote до появления нового GET /tariff
MAX_WAIT=$(( EFF_TTL + 20 ))
echo "waiting up to ${MAX_WAIT}s for TTL to expire…"
elapsed=0; step=2
while true; do
  quote_once
  now_calls="$(count_in_ext_logs 'GET /tariff')"
  new_delta=$(( now_calls - after_warm ))
  if [ "$new_delta" -ge 1 ]; then
    echo "calls after expire window: +${new_delta}"
    ok "после TTL появился новый GET /tariff"
    break
  fi
  elapsed=$(( elapsed + step ))
  [ "$elapsed" -ge "$MAX_WAIT" ] && { fail "не дождались повторного GET /tariff за ${MAX_WAIT}s"; TAR_CACHE_PASS=0; break; }
  sleep "$step"
done

# --- configs periodic refresh ---
banner "configs periodic refresh test"
barrier_now
OBS=$(( EFF_CFG*2 + 5 ))
echo "observing external-stubs logs for ~${OBS}s..."
sleep "${OBS}"
cfg_calls="$(count_in_ext_logs 'GET /configs')"
echo "GET /configs observed since barrier: ${cfg_calls}"
if [ "$cfg_calls" -ge 1 ]; then
  ok "зафиксированы периодические GET /configs (${cfg_calls})"
  CFG_PASS=1
else
  fail "не увидели фоновых GET /configs"
  CFG_PASS=0
fi

# --- summary ---
banner "summary"
[ "${TAR_CACHE_PASS:-0}" -eq 1 ] && ok "tariff cache ✔" || fail "tariff cache ✖"
[ "${CFG_PASS:-0}" -eq 1 ] && ok "configs periodic refresh ✔" || fail "configs periodic refresh ✖"

if [ "${TAR_CACHE_PASS:-0}" -eq 1 ] && [ "${CFG_PASS:-0}" -eq 1 ]; then
  echo; ok "ALL CHECKS PASSED 🎉"; exit 0
else
  echo; fail "SOME CHECKS FAILED"; exit 2
fi
