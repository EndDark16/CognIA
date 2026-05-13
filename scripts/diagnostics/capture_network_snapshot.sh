#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="${OUTPUT_FILE:-${1:-}}"
BASE_URL="${BASE_URL:-https://www.cognia.lat}"
API_PREFIX_INPUT="${API_PREFIX-__AUTO__}"
USERNAME="${USERNAME:-}"
PASSWORD="${PASSWORD:-}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-15}"
SAMPLES_PER_ENDPOINT="${SAMPLES_PER_ENDPOINT:-3}"
USER_AGENT="${DIAGNOSTIC_USER_AGENT:-CognIA-Diagnostic-Curl/1.0}"
NETWORK_CURL_SSL_NO_REVOKE="${NETWORK_CURL_SSL_NO_REVOKE:-false}"

if [[ -z "${OUTPUT_FILE}" ]]; then
  DEST="/dev/stdout"
else
  DEST="${OUTPUT_FILE}"
  mkdir -p "$(dirname "${DEST}")"
fi

BASE_URL="${BASE_URL%/}"

BASE_PATH="$(BASE_URL="${BASE_URL}" python - <<'PY'
from urllib.parse import urlparse
import os
parsed = urlparse(os.environ.get("BASE_URL", ""))
path = parsed.path.strip("/")
print("/" + path if path else "/")
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

write_line() {
  printf '%s\n' "$1" >>"${DEST}"
}

CURL_COMMON_OPTS=(-sS --max-time "${TIMEOUT_SECONDS}" -A "${USER_AGENT}")
if [[ "$(echo "${NETWORK_CURL_SSL_NO_REVOKE}" | tr '[:upper:]' '[:lower:]')" =~ ^(1|true|yes|on)$ ]]; then
  CURL_COMMON_OPTS+=(--ssl-no-revoke)
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

curl_timing_line() {
  local label="$1"
  local url="$2"
  local auth_header="${3:-}"
  local tmp_file
  tmp_file="$(mktemp)"
  local http_code="000"
  local timing
  if [[ -n "${auth_header}" ]]; then
    timing="$(curl "${CURL_COMMON_OPTS[@]}" \
      -H "${auth_header}" -o /dev/null \
      -w "http_code=%{http_code} time_namelookup=%{time_namelookup} time_connect=%{time_connect} time_appconnect=%{time_appconnect} time_starttransfer=%{time_starttransfer} time_total=%{time_total}" \
      "${url}" 2>"${tmp_file}" || true)"
  else
    timing="$(curl "${CURL_COMMON_OPTS[@]}" \
      -o /dev/null \
      -w "http_code=%{http_code} time_namelookup=%{time_namelookup} time_connect=%{time_connect} time_appconnect=%{time_appconnect} time_starttransfer=%{time_starttransfer} time_total=%{time_total}" \
      "${url}" 2>"${tmp_file}" || true)"
  fi
  http_code="$(echo "${timing}" | sed -nE 's/.*http_code=([0-9]{3}).*/\1/p')"
  write_line "${label} url=${url} ${timing}"
  local curl_error
  curl_error="$(tr '\n' ' ' <"${tmp_file}" | sed -E 's/[[:space:]]+/ /g' | sed -E 's/(Bearer )[A-Za-z0-9._-]+/\1[REDACTED]/g')"
  if [[ -n "${curl_error}" ]]; then
    write_line "${label} curl_error=${curl_error}"
  fi
  rm -f "${tmp_file}"
  [[ "${http_code}" == "200" || "${http_code}" == "401" || "${http_code}" == "403" ]] || true
}

TARGET_HOST="$(BASE_URL="${BASE_URL}" python - <<'PY'
from urllib.parse import urlparse
import os
parsed = urlparse(os.environ.get("BASE_URL", ""))
print(parsed.hostname or "")
PY
)"

TOKEN=""
if [[ -n "${USERNAME}" && -n "${PASSWORD}" ]]; then
  LOGIN_PAYLOAD="{\"identifier\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}"
  LOGIN_RAW="$(curl "${CURL_COMMON_OPTS[@]}" \
    -H "Content-Type: application/json" \
    -X POST "$(api_url /auth/login)" \
    -d "${LOGIN_PAYLOAD}" \
    -w "\n%{http_code}" || true)"
  LOGIN_STATUS="$(echo "${LOGIN_RAW}" | tail -n1)"
  LOGIN_BODY="$(echo "${LOGIN_RAW}" | sed '$d')"
  TOKEN="$(LOGIN_BODY="${LOGIN_BODY}" python - <<'PY'
import json
import os
raw = os.environ.get("LOGIN_BODY", "")
try:
    data = json.loads(raw)
except Exception:
    data = {}
print(data.get("access_token", ""))
PY
)"
  write_line "auth_login_status=${LOGIN_STATUS}"
fi

write_line "# CognIA Network Snapshot"
write_line "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
write_line "base_url=${BASE_URL}"
write_line "api_prefix=${API_PREFIX}"
write_line "target_host=${TARGET_HOST}"
write_line "samples_per_endpoint=${SAMPLES_PER_ENDPOINT}"
write_line "timeout_seconds=${TIMEOUT_SECONDS}"
write_line ""

if command -v ping >/dev/null 2>&1 && [[ -n "${TARGET_HOST}" ]]; then
  write_line "## ping"
  ping -c 4 "${TARGET_HOST}" >>"${DEST}" 2>&1 || true
  write_line ""
fi

if command -v traceroute >/dev/null 2>&1 && [[ -n "${TARGET_HOST}" ]]; then
  write_line "## traceroute"
  traceroute -m 8 "${TARGET_HOST}" >>"${DEST}" 2>&1 || true
  write_line ""
elif command -v tracepath >/dev/null 2>&1 && [[ -n "${TARGET_HOST}" ]]; then
  write_line "## tracepath"
  tracepath "${TARGET_HOST}" >>"${DEST}" 2>&1 || true
  write_line ""
fi

write_line "## curl_timing"
for i in $(seq 1 "${SAMPLES_PER_ENDPOINT}"); do
  curl_timing_line "sample=${i} endpoint=healthz" "$(root_url /healthz)"
  curl_timing_line "sample=${i} endpoint=readyz" "$(root_url /readyz)"
  if [[ -n "${TOKEN}" ]]; then
    curl_timing_line "sample=${i} endpoint=auth_me" "$(api_url /auth/me)" "Authorization: Bearer ${TOKEN}"
    curl_timing_line "sample=${i} endpoint=qv2_active" "$(api_url "/v2/questionnaires/active?mode=short&role=guardian&page=1&page_size=5")" "Authorization: Bearer ${TOKEN}"
  fi
done

if [[ "${DEST}" != "/dev/stdout" ]]; then
  echo "${DEST}"
fi
