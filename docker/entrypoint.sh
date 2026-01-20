#!/usr/bin/env bash
set -e

# Opcional: configura Gunicorn
CPU_CORES=$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)
DEFAULT_WORKERS=$((2 * CPU_CORES + 1))
WORKERS=${GUNICORN_WORKERS:-$DEFAULT_WORKERS}
THREADS=${GUNICORN_THREADS:-4}
BIND="0.0.0.0:${PORT:-5000}"

echo "==> Esperando base de datos y aplicando migraciones..."
RETRIES=${DB_RETRIES:-10}
SLEEP=${DB_RETRY_SLEEP:-3}
COUNT=0
until alembic upgrade head; do
  COUNT=$((COUNT + 1))
  if [ "$COUNT" -ge "$RETRIES" ]; then
    echo "!! No se pudo aplicar migraciones despuÃ©s de $RETRIES intentos"
    exit 1
  fi
  echo "Reintentando migraciones en ${SLEEP}s..."
  sleep "$SLEEP"
done
echo "==> Migraciones listas."

echo "==> Iniciando Gunicorn en ${BIND} con ${WORKERS} workers y ${THREADS} threads"
exec gunicorn -w "$WORKERS" --threads "$THREADS" -b "$BIND" run:app
