#!/usr/bin/env bash
set -e

# Opcional: configura Gunicorn
CPU_CORES=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)

MEM_LIMIT_MB=""
if [ -f /sys/fs/cgroup/memory.max ]; then
  MEM_RAW=$(cat /sys/fs/cgroup/memory.max)
  if [ "$MEM_RAW" != "max" ]; then
    MEM_LIMIT_MB=$(awk "BEGIN {print int($MEM_RAW/1024/1024)}")
  fi
elif [ -f /sys/fs/cgroup/memory/memory.limit_in_bytes ]; then
  MEM_RAW=$(cat /sys/fs/cgroup/memory/memory.limit_in_bytes)
  MEM_LIMIT_MB=$(awk "BEGIN {print int($MEM_RAW/1024/1024)}")
fi

# Some platforms report a huge number for "unlimited".
if [ -n "$MEM_LIMIT_MB" ] && [ "$MEM_LIMIT_MB" -gt 200000 ]; then
  MEM_LIMIT_MB=""
fi

if [ -n "$MEM_LIMIT_MB" ] && [ "$MEM_LIMIT_MB" -le 1024 ]; then
  DEFAULT_WORKERS=1
  DEFAULT_THREADS=2
elif [ -n "$MEM_LIMIT_MB" ] && [ "$MEM_LIMIT_MB" -le 2048 ]; then
  DEFAULT_WORKERS=2
  DEFAULT_THREADS=2
else
  DEFAULT_WORKERS=$((2 * CPU_CORES + 1))
  DEFAULT_THREADS=4
fi

WORKERS=${GUNICORN_WORKERS:-${WEB_CONCURRENCY:-$DEFAULT_WORKERS}}
THREADS=${GUNICORN_THREADS:-$DEFAULT_THREADS}
BIND="0.0.0.0:${PORT:-5000}"

should_run_migrations() {
  local run_flag="${RUN_MIGRATIONS:-1}"
  local skip_flag="${SKIP_MIGRATIONS:-0}"

  if [[ "$skip_flag" =~ ^(1|true|TRUE|yes|YES)$ ]]; then
    return 1
  fi
  if [[ "$run_flag" =~ ^(0|false|FALSE|no|NO)$ ]]; then
    return 1
  fi
  return 0
}

if should_run_migrations; then
  echo "==> Esperando base de datos y aplicando migraciones..."
  RETRIES=${DB_RETRIES:-10}
  SLEEP=${DB_RETRY_SLEEP:-3}
  COUNT=0
  until alembic upgrade head; do
    COUNT=$((COUNT + 1))
    if [ "$COUNT" -ge "$RETRIES" ]; then
      echo "!! No se pudo aplicar migraciones despues de $RETRIES intentos"
      exit 1
    fi
    echo "Reintentando migraciones en ${SLEEP}s..."
    sleep "$SLEEP"
  done
  echo "==> Migraciones listas."
else
  echo "==> Migraciones deshabilitadas (RUN_MIGRATIONS=false o SKIP_MIGRATIONS=true)."
fi

echo "==> Iniciando Gunicorn en ${BIND} con ${WORKERS} workers y ${THREADS} threads"
exec gunicorn -w "$WORKERS" --threads "$THREADS" -b "$BIND" run:app
