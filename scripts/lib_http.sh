#!/usr/bin/env bash
# shellcheck shell=bash

# Жёсткие дефолты
set -euo pipefail

: "${BASE_URL:=http://localhost:8000}"
: "${SHOW_LOGS_ON_FAIL:=0}"

HTTP_STATUS=""

# Внутренняя функция HTTP-запроса.
# usage: _http_request METHOD PATH_OR_URL [DATA_JSON] [HEADER "Name: Val"]...
#  - PATH_OR_URL: абсолютный URL или относительный путь (склеится с BASE_URL)
#  - DATA_JSON:   опционально. Если первый "хвостовой" аргумент выглядит как "X: Y",
#                 то считаем, что тела нет и это сразу заголовок.
_http_request() {
  local method="$1"
  local path_or_url="$2"
  shift 2

  # Определим, что у нас первым идёт: тело или заголовок
  local data=""
  if [[ $# -gt 0 ]]; then
    # первый "хвостовой" аргумент
    local maybe_body="${1-}"
    # если похоже на "Header: value", то тела нет
    if [[ "${maybe_body}" =~ ^[[:alnum:]-]+:[[:space:]] ]]; then
      data=""
    else
      data="${maybe_body}"
      shift
    fi
  fi

  # Остальные аргументы — заголовки "Name: value"
  local -a extra_headers=()
  while [[ $# -gt 0 ]]; do
    extra_headers+=("$1")
    shift
  done

  # Собираем URL
  local url
  if [[ "${path_or_url}" =~ ^https?:// ]]; then
    url="${path_or_url}"
  else
    local base="${BASE_URL%/}"
    if [[ "${path_or_url}" = /* ]]; then
      url="${base}${path_or_url}"
    else
      url="${base}/${path_or_url}"
    fi
  fi

  # Базовые заголовки
  local -a headers=("Accept: application/json")
  if [[ -n "${data}" && "${method}" != "GET" ]]; then
    headers+=("Content-Type: application/json")
  fi
  # Пользовательские заголовки (безопасная распаковка при set -u)
  for h in ${extra_headers[@]+"${extra_headers[@]}"}; do
    headers+=("$h")
  done

  # Преобразуем в флаги curl
  local -a header_flags=()
  for h in "${headers[@]}"; do
    header_flags+=(-H "$h")
  done

  # Команда curl
  local -a curl_cmd=(curl -sS -w $'\n%{http_code}' -X "${method}")
  curl_cmd+=("${header_flags[@]}")
  if [[ -n "${data}" ]]; then
    curl_cmd+=(--data-binary "${data}")
  fi
  curl_cmd+=("${url}")

  # Выполнение
  local raw
  if ! raw="$("${curl_cmd[@]}" 2>&1)"; then
    echo "[HTTP] ${method} ${url} -> curl failed" >&2
    echo "${raw}" >&2
    return 1
  fi

  local code body
  code="${raw##*$'\n'}"
  body="${raw%$'\n'*}"

  HTTP_STATUS="${code}"
  echo "[HTTP] ${method} ${url} -> ${code}" >&2
  printf '%s' "${body}"

  if [[ ! "${code}" =~ ^2[0-9][0-9]$ ]]; then
    if [[ "${SHOW_LOGS_ON_FAIL}" == "1" ]]; then
      echo >&2
      echo "--- response body (non-2xx) ---" >&2
      echo "${body}" >&2
      echo "-------------------------------" >&2
    fi
    return 1
  fi
  return 0
}

# Публичные обёртки. НИЧЕГО не "едим" — передаём хвост как есть.
# GET: http_get_json PATH_OR_URL [HEADER ...]
http_get_json() {
  local path_or_url="$1"; shift || true
  _http_request "GET" "${path_or_url}" "$@"
}

# POST: http_post_json PATH_OR_URL [DATA_JSON] [HEADER ...]
http_post_json() {
  local path_or_url="$1"; shift || true
  _http_request "POST" "${path_or_url}" "$@"
}

# PUT: http_put_json PATH_OR_URL [DATA_JSON] [HEADER ...]
http_put_json() {
  local path_or_url="$1"; shift || true
  _http_request "PUT" "${path_or_url}" "$@"
}

# DELETE: http_delete_json PATH_OR_URL [DATA_JSON] [HEADER ...]
http_delete_json() {
  local path_or_url="$1"; shift || true
  _http_request "DELETE" "${path_or_url}" "$@"
}