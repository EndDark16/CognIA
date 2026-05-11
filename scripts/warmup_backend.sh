#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://www.cognia.lat}"
API_PREFIX_INPUT="${API_PREFIX-__AUTO__}"
USERNAME="${USERNAME:-}"
PASSWORD="${PASSWORD:-}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-10}"
SAFE_MODE="${SAFE_MODE:-true}"
WARMUP_MODES="${WARMUP_MODES:-short,medium}"
WARMUP_ROLES="${WARMUP_ROLES:-guardian,psychologist}"
WARMUP_USER_AGENT="${WARMUP_USER_AGENT:-CognIA-Warmup-Curl/1.0}"

if [[ ! "${SAFE_MODE,,}" =~ ^(1|true|yes|on)$ ]]; then
  echo "SAFE_MODE=false is not allowed for warmup_backend.sh"
  exit 2
fi

trim_slashes() {
  local value="$1"
  value="${value#/}"
  value="${value%/}"
  echo "$value"
}

BASE_URL="${BASE_URL%/}"
BASE_PATH="$(python - <<'PY'
from urllib.parse import urlparse
import os
base = os.environ.get('BASE_URL','')
parsed = urlparse(base)
path = '/'+parsed.path.strip('/') if parsed.path.strip('/') else '/'
print(path)
PY
)"

if [[ "${API_PREFIX_INPUT}" == "__AUTO__" ]]; then
  if [[ "${BASE_PATH}" == "/api" ]]; then
    API_PREFIX=""
  else
    API_PREFIX="/api"
  fi
else
  API_PREFIX="${API_PREFIX_INPUT}"
fi

if [[ -n "${API_PREFIX}" ]]; then
  [[ "${API_PREFIX}" == /* ]] || API_PREFIX="/${API_PREFIX}"
  API_PREFIX="${API_PREFIX%/}"
fi

if [[ "${BASE_PATH}" != "/" && "${BASE_PATH}" == "${API_PREFIX}" ]]; then
  API_PREFIX=""
fi

root_url() {
  local path="$1"
  [[ "${path}" == /* ]] || path="/${path}"
  echo "${BASE_URL}${path}"
}

api_url() {
  local path="$1"
  [[ "${path}" == /* ]] || path="/${path}"
  echo "${BASE_URL}${API_PREFIX}${path}"
}

curl_json_status() {
  local method="$1"
  local url="$2"
  local data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -sS --max-time "${TIMEOUT_SECONDS}" -A "${WARMUP_USER_AGENT}" -X "$method" \
      -H "Content-Type: application/json" \
      -d "$data" \
      -w "\n%{http_code}" \
      "$url"
  else
    curl -sS --max-time "${TIMEOUT_SECONDS}" -A "${WARMUP_USER_AGENT}" -X "$method" \
      -w "\n%{http_code}" \
      "$url"
  fi
}

check_200() {
  local label="$1"
  local url="$2"
  local response
  response="$(curl_json_status GET "$url")"
  local status
  status="$(echo "$response" | tail -n1)"
  if [[ "$status" != "200" ]]; then
    echo "Warmup failed at ${label} status=${status}"
    exit 1
  fi
  echo "${label}: ${status}"
}

check_200 "healthz" "$(root_url /healthz)"
check_200 "readyz" "$(root_url /readyz)"

ACCESS_TOKEN=""
if [[ -n "${USERNAME}" && -n "${PASSWORD}" ]]; then
  LOGIN_PAYLOAD="{\"identifier\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}"
  LOGIN_RESPONSE="$(curl_json_status POST "$(api_url /auth/login)" "$LOGIN_PAYLOAD")"
  LOGIN_STATUS="$(echo "$LOGIN_RESPONSE" | tail -n1)"
  LOGIN_BODY="$(echo "$LOGIN_RESPONSE" | sed '$d')"
  if [[ "$LOGIN_STATUS" != "200" ]]; then
    echo "Warmup login failed status=${LOGIN_STATUS}"
    exit 1
  fi
  ACCESS_TOKEN="$(echo "$LOGIN_BODY" | python - <<'PY'
import json,sys
raw=sys.stdin.read().strip()
try:
    data=json.loads(raw)
except Exception:
    data={}
print(data.get('access_token',''))
PY
)"
  if [[ -z "${ACCESS_TOKEN}" ]]; then
    echo "Warmup login returned no access token"
    exit 1
  fi
  echo "auth/login: 200"
fi

if [[ -n "${ACCESS_TOKEN}" ]]; then
  auth_get() {
    local label="$1"
    local url="$2"
    local response
    response="$(curl -sS --max-time "${TIMEOUT_SECONDS}" -A "${WARMUP_USER_AGENT}" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      -w "\n%{http_code}" \
      "$url")"
    local status
    status="$(echo "$response" | tail -n1)"
    if [[ "$status" != "200" ]]; then
      echo "Warmup failed at ${label} status=${status}"
      exit 1
    fi
    echo "${label}: ${status}"
  }

  auth_get "auth/me" "$(api_url /auth/me)"
  auth_get "v2/security/transport-key" "$(api_url /v2/security/transport-key)"

  IFS=',' read -r -a modes <<< "$WARMUP_MODES"
  IFS=',' read -r -a roles <<< "$WARMUP_ROLES"
  for role in "${roles[@]}"; do
    role="$(echo "$role" | xargs)"
    for mode in "${modes[@]}"; do
      mode="$(echo "$mode" | xargs)"
      [[ -n "$role" && -n "$mode" ]] || continue
      auth_get "qv2_active:${role}:${mode}" "$(api_url "/v2/questionnaires/active?mode=${mode}&role=${role}&page=1&page_size=5")"
    done
  done
fi

echo "Warmup completed base_url=${BASE_URL} api_prefix=${API_PREFIX:-<empty>}"
