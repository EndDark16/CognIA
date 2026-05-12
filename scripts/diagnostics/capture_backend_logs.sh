#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="${OUTPUT_FILE:-${1:-}}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"
LOG_SINCE="${LOG_SINCE:-15m}"
LOG_TAIL_LINES="${LOG_TAIL_LINES:-1200}"
SOURCE_LOG_FILE="${SOURCE_LOG_FILE:-}"

if [[ -z "${OUTPUT_FILE}" ]]; then
  DEST="/dev/stdout"
else
  DEST="${OUTPUT_FILE}"
  mkdir -p "$(dirname "${DEST}")"
fi

RAW_LOG_FILE="$(mktemp)"
SANITIZED_LOG_FILE="$(mktemp)"

cleanup() {
  rm -f "${RAW_LOG_FILE}" "${SANITIZED_LOG_FILE}"
}
trap cleanup EXIT

write_line() {
  printf '%s\n' "$1" >>"${DEST}"
}

sanitize_stream() {
  sed -E \
    -e 's/(Authorization:[[:space:]]+Bearer[[:space:]]+)[A-Za-z0-9._-]+/\1[REDACTED]/Ig' \
    -e 's/("?(access_token|refresh_token|id_token)"?[[:space:]]*[:=][[:space:]]*")[^"]+/\1[REDACTED]/Ig' \
    -e 's/("?(password|passwd|secret|token)"?[[:space:]]*[:=][[:space:]]*")[^"]+/\1[REDACTED]/Ig' \
    -e "s/('?(access_token|refresh_token|id_token)'?[[:space:]]*[:=][[:space:]]*')[^']+/\1[REDACTED]/Ig" \
    -e "s/('?(password|passwd|secret|token)'?[[:space:]]*[:=][[:space:]]*')[^']+/\1[REDACTED]/Ig"
}

collect_logs() {
  if [[ -n "${SOURCE_LOG_FILE}" && -f "${SOURCE_LOG_FILE}" ]]; then
    tail -n "${LOG_TAIL_LINES}" "${SOURCE_LOG_FILE}" >"${RAW_LOG_FILE}" 2>/dev/null || true
    return 0
  fi

  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    local tmp_services
    tmp_services="$(mktemp)"
    if docker compose config --services >"${tmp_services}" 2>/dev/null; then
      if grep -qx "${BACKEND_SERVICE}" "${tmp_services}"; then
        docker compose logs --since "${LOG_SINCE}" "${BACKEND_SERVICE}" >"${RAW_LOG_FILE}" 2>&1 || true
      else
        docker compose logs --tail "${LOG_TAIL_LINES}" >"${RAW_LOG_FILE}" 2>&1 || true
      fi
      rm -f "${tmp_services}"
      return 0
    fi
    rm -f "${tmp_services}"
  fi

  if command -v docker >/dev/null 2>&1; then
    local container_name
    container_name="$(docker ps --format '{{.Names}}' | grep -E "${BACKEND_SERVICE}|cognia.*backend|backend" | head -n1 || true)"
    if [[ -n "${container_name}" ]]; then
      docker logs --since "${LOG_SINCE}" "${container_name}" >"${RAW_LOG_FILE}" 2>&1 || true
      return 0
    fi
  fi

  return 1
}

count_pattern() {
  local pattern="$1"
  grep -Eic "${pattern}" "${SANITIZED_LOG_FILE}" || true
}

collect_logs || true
cat "${RAW_LOG_FILE}" | sanitize_stream >"${SANITIZED_LOG_FILE}" || true

write_line "# CognIA Backend Log Snapshot"
write_line "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
write_line "backend_service=${BACKEND_SERVICE}"
write_line "log_since=${LOG_SINCE}"
write_line "log_tail_lines=${LOG_TAIL_LINES}"
write_line ""
write_line "## Detection summary"
write_line "- db_or_pool_signals_count=$(count_pattern 'db_unavailable|database error|sqlalchemy|queuepool|pool_timeout|operationalerror|psycopg|timeout')"
write_line "- rate_limited_count=$(count_pattern 'rate_limited|too many requests|status=429| 429 ')"
write_line "- server_error_count=$(count_pattern 'server_error|status=5[0-9]{2}|\" 5[0-9]{2} ')"
write_line "- client_error_count=$(count_pattern 'status=4[0-9]{2}|\" 4[0-9]{2} ')"
write_line "- gunicorn_timeout_count=$(count_pattern 'worker timeout|gunicorn|timeout \\(.*worker\\)|harakiri')"
write_line "- startup_or_migration_issues_count=$(count_pattern 'alembic|migration|traceback|modulenotfounderror|importerror')"
write_line "- request_id_mentions_count=$(count_pattern 'request_id=|x-request-id')"
write_line ""

write_line "## Matched log lines (critical patterns)"
{
  grep -Eni 'db_unavailable|database error|sqlalchemy|queuepool|pool_timeout|operationalerror|psycopg|worker timeout|gunicorn|rate_limited|server_error|status=5[0-9]{2}|status=4[0-9]{2}|alembic|migration|request_id=' "${SANITIZED_LOG_FILE}" || true
} | tail -n 300 >>"${DEST}"

write_line ""
write_line "## Sanitized raw tail"
tail -n "${LOG_TAIL_LINES}" "${SANITIZED_LOG_FILE}" >>"${DEST}" || true

if [[ "${DEST}" != "/dev/stdout" ]]; then
  echo "${DEST}"
fi
