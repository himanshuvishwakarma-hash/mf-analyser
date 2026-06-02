#!/bin/sh
# Z1N MF Analyser - backend container entrypoint.
#
# Responsibilities (in order):
#   1. Wait for Postgres to accept connections (10 retries × 3 s).
#   2. Run alembic migrations to head. Fatal on failure.
#   3. exec the original CMD (uvicorn for backend, celery for worker).
#
# Both backend and worker containers share this image and entrypoint.
# Only the backend (uvicorn) needs migrations to be applied; running alembic
# from the worker is harmless (idempotent + same head check) and guarantees
# the schema is ready even if the worker boots first.

set -e

PG_HOST="${POSTGRES_HOST:-postgres}"
PG_PORT="${POSTGRES_PORT:-5432}"

echo "[entrypoint] waiting for postgres at ${PG_HOST}:${PG_PORT}..."
for i in $(seq 1 30); do
  if python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('${PG_HOST}', ${PG_PORT}))
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    echo "[entrypoint] postgres reachable after ${i}s"
    break
  fi
  echo "[entrypoint] postgres not ready, retry ${i}/30"
  sleep 2
done

if [ "${SKIP_MIGRATIONS:-0}" = "1" ]; then
  echo "[entrypoint] SKIP_MIGRATIONS=1, not running alembic (worker container)"
else
  echo "[entrypoint] running alembic migrations..."
  alembic upgrade head
  echo "[entrypoint] migrations OK"
fi

echo "[entrypoint] starting: $@"
exec "$@"
