#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SCENARIO="${SCENARIO:-diagnostic_health_vs_api}"
BASE_URL="${BASE_URL:-https://www.cognia.lat}"
API_PREFIX="${API_PREFIX:-/api}"
USERNAME="${USERNAME:-}"
PASSWORD="${PASSWORD:-}"
SAFE_MODE="${SAFE_MODE:-true}"
REQUIRE_AUTH="${REQUIRE_AUTH:-true}"
TEST_RUN_ID="${TEST_RUN_ID:-a4_diag_$(date -u +%Y%m%dT%H%M%SZ)}"
VUS="${VUS:-${K6_VUS:-10}}"
DURATION="${DURATION:-${K6_DURATION:-5m}}"
K6_SCRIPT_INPUT="${K6_SCRIPT:-}"
ENABLE_DURING_SNAPSHOT="${ENABLE_DURING_SNAPSHOT:-true}"
DURING_DELAY_SECONDS="${DURING_DELAY_SECONDS:-90}"
RUN_WARMUP="${RUN_WARMUP:-true}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_ROOT}/artifacts/diagnostics}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"

sanitize_id() {
  echo "$1" | sed -E 's/[^A-Za-z0-9._-]+/_/g' | cut -c1-80
}

bool_is_true() {
  local value
  value="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
  [[ "${value}" =~ ^(1|true|yes|on)$ ]]
}

to_k6_runtime_path() {
  local path="$1"
  if command -v cygpath >/dev/null 2>&1; then
    case "$(uname -s 2>/dev/null || true)" in
      MINGW*|MSYS*|CYGWIN*)
        cygpath -w "${path}"
        return 0
        ;;
    esac
  fi
  echo "${path}"
}

resolve_k6_script() {
  if [[ -n "${K6_SCRIPT_INPUT}" ]]; then
    echo "${K6_SCRIPT_INPUT}"
    return 0
  fi

  case "${SCENARIO}" in
    diagnostic_health_vs_api)
      echo "scripts/load/k6_diagnostic_health_vs_api.js"
      ;;
    diagnostic_auth_vs_qv2)
      echo "scripts/load/k6_diagnostic_auth_vs_qv2.js"
      ;;
    diagnostic_ladder_short)
      echo "scripts/load/k6_diagnostic_ladder_short.js"
      ;;
    diagnostic_soak_light)
      echo "scripts/load/k6_diagnostic_soak_light.js"
      ;;
    *)
      echo "scripts/load/k6_diagnostic_health_vs_api.js"
      ;;
  esac
}

log() {
  printf '[A4-DIAG] %s\n' "$1"
}

K6_SCRIPT_REL="$(resolve_k6_script)"
if [[ "${K6_SCRIPT_REL}" = /* ]]; then
  K6_SCRIPT_PATH="${K6_SCRIPT_REL}"
else
  K6_SCRIPT_PATH="${REPO_ROOT}/${K6_SCRIPT_REL}"
fi

if [[ ! -f "${K6_SCRIPT_PATH}" ]]; then
  echo "k6 script not found: ${K6_SCRIPT_PATH}" >&2
  exit 2
fi

RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_ID_SAFE="$(sanitize_id "${TEST_RUN_ID}")"
SCENARIO_SAFE="$(sanitize_id "${SCENARIO}")"
RUN_DIR="${OUTPUT_ROOT}/${RUN_TS}_${SCENARIO_SAFE}_${RUN_ID_SAFE}"
mkdir -p "${RUN_DIR}/k6_handle_summary"

log "run_dir=${RUN_DIR}"

cat >"${RUN_DIR}/run_context.env" <<EOF
timestamp_utc=${RUN_TS}
scenario=${SCENARIO}
test_run_id=${TEST_RUN_ID}
base_url=${BASE_URL}
api_prefix=${API_PREFIX}
vus=${VUS}
duration=${DURATION}
safe_mode=${SAFE_MODE}
require_auth=${REQUIRE_AUTH}
k6_script=${K6_SCRIPT_PATH}
backend_service=${BACKEND_SERVICE}
EOF

if bool_is_true "${RUN_WARMUP}" && [[ -x "${REPO_ROOT}/scripts/warmup_backend.sh" ]]; then
  log "running warmup"
  (
    cd "${REPO_ROOT}"
    BASE_URL="${BASE_URL}" \
    API_PREFIX="${API_PREFIX}" \
    USERNAME="${USERNAME}" \
    PASSWORD="${PASSWORD}" \
    SAFE_MODE="${SAFE_MODE}" \
    "${REPO_ROOT}/scripts/warmup_backend.sh"
  ) >"${RUN_DIR}/warmup.log" 2>&1 || true
fi

log "capturing before snapshots"
OUTPUT_FILE="${RUN_DIR}/host_before.txt" BACKEND_SERVICE="${BACKEND_SERVICE}" "${SCRIPT_DIR}/capture_host_snapshot.sh" >/dev/null 2>&1 || true
OUTPUT_FILE="${RUN_DIR}/backend_logs_before.txt" BACKEND_SERVICE="${BACKEND_SERVICE}" "${SCRIPT_DIR}/capture_backend_logs.sh" >/dev/null 2>&1 || true
OUTPUT_FILE="${RUN_DIR}/network_before.txt" BASE_URL="${BASE_URL}" API_PREFIX="${API_PREFIX}" USERNAME="${USERNAME}" PASSWORD="${PASSWORD}" "${SCRIPT_DIR}/capture_network_snapshot.sh" >/dev/null 2>&1 || true

DURING_PID=""
if bool_is_true "${ENABLE_DURING_SNAPSHOT}"; then
  log "scheduling during snapshot in ${DURING_DELAY_SECONDS}s"
  (
    sleep "${DURING_DELAY_SECONDS}"
    OUTPUT_FILE="${RUN_DIR}/host_during.txt" BACKEND_SERVICE="${BACKEND_SERVICE}" "${SCRIPT_DIR}/capture_host_snapshot.sh" >/dev/null 2>&1 || true
    OUTPUT_FILE="${RUN_DIR}/backend_logs_during.txt" BACKEND_SERVICE="${BACKEND_SERVICE}" "${SCRIPT_DIR}/capture_backend_logs.sh" >/dev/null 2>&1 || true
    OUTPUT_FILE="${RUN_DIR}/network_during.txt" BASE_URL="${BASE_URL}" API_PREFIX="${API_PREFIX}" USERNAME="${USERNAME}" PASSWORD="${PASSWORD}" "${SCRIPT_DIR}/capture_network_snapshot.sh" >/dev/null 2>&1 || true
  ) &
  DURING_PID="$!"
fi

K6_SUMMARY_FILE="${RUN_DIR}/k6_summary_export.json"
K6_RAW_FILE="${RUN_DIR}/k6_raw_output.json"
K6_STDOUT_FILE="${RUN_DIR}/k6_stdout.log"
K6_EXIT_CODE=0
K6_SCRIPT_RUNTIME_PATH="$(to_k6_runtime_path "${K6_SCRIPT_PATH}")"
K6_SUMMARY_RUNTIME_PATH="$(to_k6_runtime_path "${K6_SUMMARY_FILE}")"
K6_RAW_RUNTIME_PATH="$(to_k6_runtime_path "${K6_RAW_FILE}")"
K6_OUTPUT_DIR_RUNTIME_PATH="$(to_k6_runtime_path "${RUN_DIR}/k6_handle_summary")"

log "running k6 scenario"
(
  cd "${REPO_ROOT}"
  BASE_URL="${BASE_URL}" \
  API_PREFIX="${API_PREFIX}" \
  USERNAME="${USERNAME}" \
  PASSWORD="${PASSWORD}" \
  SAFE_MODE="${SAFE_MODE}" \
  REQUIRE_AUTH="${REQUIRE_AUTH}" \
  TEST_RUN_ID="${TEST_RUN_ID}" \
  K6_VUS="${VUS}" \
  K6_DURATION="${DURATION}" \
  K6_OUTPUT_DIR="${K6_OUTPUT_DIR_RUNTIME_PATH}" \
  k6 run \
    --summary-export "${K6_SUMMARY_RUNTIME_PATH}" \
    --out "json=${K6_RAW_RUNTIME_PATH}" \
    "${K6_SCRIPT_RUNTIME_PATH}"
) >"${K6_STDOUT_FILE}" 2>&1 || K6_EXIT_CODE=$?

echo "${K6_EXIT_CODE}" >"${RUN_DIR}/k6_exit_code.txt"
log "k6 exit_code=${K6_EXIT_CODE}"

if [[ -n "${DURING_PID}" ]]; then
  wait "${DURING_PID}" || true
fi

log "capturing after snapshots"
OUTPUT_FILE="${RUN_DIR}/host_after.txt" BACKEND_SERVICE="${BACKEND_SERVICE}" "${SCRIPT_DIR}/capture_host_snapshot.sh" >/dev/null 2>&1 || true
OUTPUT_FILE="${RUN_DIR}/backend_logs_after.txt" BACKEND_SERVICE="${BACKEND_SERVICE}" "${SCRIPT_DIR}/capture_backend_logs.sh" >/dev/null 2>&1 || true
OUTPUT_FILE="${RUN_DIR}/network_after.txt" BASE_URL="${BASE_URL}" API_PREFIX="${API_PREFIX}" USERNAME="${USERNAME}" PASSWORD="${PASSWORD}" "${SCRIPT_DIR}/capture_network_snapshot.sh" >/dev/null 2>&1 || true

if [[ -f "${SCRIPT_DIR}/analyze_diagnostic_run.py" ]]; then
  log "running diagnostic analyzer"
  ANALYZER_SCRIPT_RUNTIME_PATH="$(to_k6_runtime_path "${SCRIPT_DIR}/analyze_diagnostic_run.py")"
  RUN_DIR_RUNTIME_PATH="$(to_k6_runtime_path "${RUN_DIR}")"
  ANALYZER_OUTPUT_RUNTIME_PATH="$(to_k6_runtime_path "${RUN_DIR}/diagnostic_analysis.md")"
  (
    cd "${REPO_ROOT}"
    python "${ANALYZER_SCRIPT_RUNTIME_PATH}" \
      --run-dir "${RUN_DIR_RUNTIME_PATH}" \
      --output "${ANALYZER_OUTPUT_RUNTIME_PATH}"
  ) >"${RUN_DIR}/analyzer.log" 2>&1 || true
fi

python - "${RUN_DIR}" <<'PY' >"${RUN_DIR}/run_summary.md"
import json
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
summary = run_dir / "k6_summary_export.json"
context = run_dir / "run_context.env"
exit_code_file = run_dir / "k6_exit_code.txt"

def metric(data, name, field):
    metric_obj = (((data or {}).get("metrics") or {}).get(name) or {})
    values = metric_obj.get("values")
    if isinstance(values, dict) and field in values:
        return values.get(field)
    return metric_obj.get(field)

data = {}
if summary.exists():
    try:
        data = json.loads(summary.read_text(encoding="utf-8"))
    except Exception:
        data = {}

exit_code = "unknown"
if exit_code_file.exists():
    exit_code = exit_code_file.read_text(encoding="utf-8").strip()

context_lines = []
if context.exists():
    context_lines = [line.strip() for line in context.read_text(encoding="utf-8").splitlines() if line.strip()]

print("# A4 Diagnostic Window Summary")
print("")
for line in context_lines:
    print(f"- {line}")
print(f"- k6_exit_code={exit_code}")
print("")
print("## k6 highlights")
print(f"- http_req_failed_rate={metric(data, 'http_req_failed', 'rate')}")
print(f"- http_reqs_rate={metric(data, 'http_reqs', 'rate')}")
print(f"- latency_p95_ms={metric(data, 'http_req_duration', 'p(95)')}")
print(f"- latency_p99_ms={metric(data, 'http_req_duration', 'p(99)')}")
print("")
print("## Artifacts")
for item in sorted(run_dir.glob("*")):
    if item.is_file():
        print(f"- {item.name}")
print("- k6_handle_summary/")
PY

echo "${RUN_DIR}"
exit "${K6_EXIT_CODE}"
