#!/usr/bin/env bash
set -euo pipefail

OUTPUT_FILE="${OUTPUT_FILE:-${1:-}}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"
LOG_TAIL_LINES="${LOG_TAIL_LINES:-200}"

if [[ -z "${OUTPUT_FILE}" ]]; then
  DEST="/dev/stdout"
else
  DEST="${OUTPUT_FILE}"
  mkdir -p "$(dirname "${DEST}")"
fi

sanitize_stream() {
  sed -E \
    -e 's/(Authorization:[[:space:]]+Bearer[[:space:]]+)[A-Za-z0-9._-]+/\1[REDACTED]/Ig' \
    -e 's/("?(access_token|refresh_token|id_token)"?[[:space:]]*[:=][[:space:]]*")[^"]+/\1[REDACTED]/Ig' \
    -e 's/("?(password|passwd|secret|token)"?[[:space:]]*[:=][[:space:]]*")[^"]+/\1[REDACTED]/Ig'
}

write_line() {
  printf '%s\n' "$1" >>"${DEST}"
}

run_section() {
  local title="$1"
  shift
  write_line ""
  write_line "## ${title}"
  write_line "\$ $*"
  if "$@" 2>&1 | sanitize_stream >>"${DEST}"; then
    :
  else
    local code="${PIPESTATUS[0]:-1}"
    write_line "(command failed exit=${code})"
  fi
}

run_optional_section() {
  local title="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    run_section "${title}" "$@"
  fi
}

write_line "# CognIA Host Snapshot"
run_section "timestamp_utc" date -u +"%Y-%m-%dT%H:%M:%SZ"
run_section "hostname" hostname
run_section "uname" uname -a
run_section "uptime" uptime

OS_NAME="$(uname -s || echo unknown)"
if [[ "${OS_NAME}" == "Darwin" ]]; then
  run_optional_section "cpu_sysctl" sysctl -n machdep.cpu.brand_string
  run_section "top_l1" top -l 1
  run_section "vm_stat" vm_stat
  run_optional_section "swap_usage" sysctl vm.swapusage
  run_optional_section "memory_pressure" memory_pressure
  run_section "df_h" df -h
  run_optional_section "netstat_ib" netstat -ib
  run_section "ps_top_cpu_mem" sh -c "ps -axo pid,ppid,%cpu,%mem,etime,comm | head -n 30"
else
  run_optional_section "cpu_lscpu" lscpu
  run_optional_section "loadavg" cat /proc/loadavg
  run_optional_section "top_b_n1" top -b -n 1
  run_optional_section "free_m" free -m
  run_optional_section "swap_proc" cat /proc/swaps
  run_optional_section "vmstat_1_5" vmstat 1 5
  run_optional_section "iostat_xz_1_3" iostat -xz 1 3
  run_section "df_h" df -h
  if command -v ss >/dev/null 2>&1; then
    run_section "ss_summary" ss -s
  elif command -v netstat >/dev/null 2>&1; then
    run_section "netstat_summary" netstat -s
  fi
  run_section "ps_top_cpu_mem" sh -c "ps -eo pid,ppid,%cpu,%mem,etime,comm --sort=-%cpu | head -n 30"
fi

if command -v docker >/dev/null 2>&1; then
  run_section "docker_ps" docker ps --no-trunc
  run_section "docker_stats_no_stream" docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}"
  if docker compose version >/dev/null 2>&1; then
    run_section "docker_compose_ps" docker compose ps

    tmp_services="$(mktemp)"
    if docker compose config --services >"${tmp_services}" 2>/dev/null; then
      if grep -qx "${BACKEND_SERVICE}" "${tmp_services}"; then
        run_section "docker_compose_logs_${BACKEND_SERVICE}_tail_${LOG_TAIL_LINES}" docker compose logs --tail "${LOG_TAIL_LINES}" "${BACKEND_SERVICE}"
      else
        run_section "docker_compose_logs_tail_${LOG_TAIL_LINES}" docker compose logs --tail "${LOG_TAIL_LINES}"
      fi
    fi
    rm -f "${tmp_services}"
  fi
fi

if [[ "${DEST}" != "/dev/stdout" ]]; then
  echo "${DEST}"
fi
