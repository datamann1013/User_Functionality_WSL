#!/usr/bin/env bash
set -euo pipefail

# Usage: start_core_memory.sh [migrate]
# If 'migrate' is passed, run migrations and exit.
# Otherwise start the uvicorn server.

if [ "${1:-}" = "migrate" ]; then
  echo "Running migrations..."
  python /app/migrate.py
  echo "Migrations completed."
  exit 0
fi

IN_CONTAINER=0
if [ -f "/.dockerenv" ]; then
  IN_CONTAINER=1
fi

if [ -f docker-compose.dev.yml ] && [ "$IN_CONTAINER" -eq 0 ]; then
  echo "Starting CoreMemory dev stack via docker-compose (detached)..."
  docker-compose -f docker-compose.dev.yml up --build -d
  echo "To run migrations in the core container:"
  echo "  docker-compose -f docker-compose.dev.yml exec -T core_memory python /app/migrate.py"
  exit 0
fi

echo "Starting uvicorn server (in-container or no docker-compose present)..."
exec uvicorn core_memory.app:app --host 0.0.0.0 --port 5010
