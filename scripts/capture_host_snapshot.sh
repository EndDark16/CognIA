#!/usr/bin/env bash
set -euo pipefail

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "# CognIA host snapshot"
echo "timestamp_utc=${TS}"

echo "\n## uname"
uname -a || true

echo "\n## uptime"
uptime || true

echo "\n## memory"
if command -v free >/dev/null 2>&1; then
  free -h || true
elif command -v vm_stat >/dev/null 2>&1; then
  vm_stat || true
fi

echo "\n## disk"
df -h || true

echo "\n## network summary"
if command -v netstat >/dev/null 2>&1; then
  netstat -i || true
fi

echo "\n## docker compose ps"
if command -v docker >/dev/null 2>&1; then
  docker compose ps || true
  echo "\n## docker stats (no-stream)"
  docker stats --no-stream || true
fi
