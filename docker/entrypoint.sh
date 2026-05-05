#!/usr/bin/env bash
set -e

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

DEFAULT_WORKERS=3
DEFAULT_THREADS=2

# Conservative fallback for constrained containers.
if [ -n "$MEM_LIMIT_MB" ] && [ "$MEM_LIMIT_MB" -le 1024 ]; then
  DEFAULT_WORKERS=2
  DEFAULT_THREADS=2
fi

if [ "$CPU_CORES" -le 1 ] && [ "$DEFAULT_WORKERS" -gt 2 ]; then
  DEFAULT_WORKERS=2
fi

BIND="0.0.0.0:${PORT:-5000}"
WORKERS=${GUNICORN_WORKERS:-${WEB_CONCURRENCY:-$DEFAULT_WORKERS}}
THREADS=${GUNICORN_THREADS:-$DEFAULT_THREADS}
WORKER_CLASS=${GUNICORN_WORKER_CLASS:-gthread}
TIMEOUT=${GUNICORN_TIMEOUT:-60}
GRACEFUL_TIMEOUT=${GUNICORN_GRACEFUL_TIMEOUT:-30}
KEEPALIVE=${GUNICORN_KEEPALIVE:-5}
MAX_REQUESTS=${GUNICORN_MAX_REQUESTS:-1000}
MAX_REQUESTS_JITTER=${GUNICORN_MAX_REQUESTS_JITTER:-100}

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

echo "==> Iniciando Gunicorn bind=${BIND} workers=${WORKERS} threads=${THREADS} class=${WORKER_CLASS} timeout=${TIMEOUT}s keepalive=${KEEPALIVE}s"
exec gunicorn run:app \
  --bind "$BIND" \
  --worker-class "$WORKER_CLASS" \
  --workers "$WORKERS" \
  --threads "$THREADS" \
  --timeout "$TIMEOUT" \
  --graceful-timeout "$GRACEFUL_TIMEOUT" \
  --keep-alive "$KEEPALIVE" \
  --max-requests "$MAX_REQUESTS" \
  --max-requests-jitter "$MAX_REQUESTS_JITTER" \
  --access-logfile - \
  --error-logfile -
