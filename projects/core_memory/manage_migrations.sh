#!/usr/bin/env bash
set -euo pipefail

# Run alembic migrations using POSTGRES_DSN env var
if [ -z "${POSTGRES_DSN:-}" ]; then
  echo "POSTGRES_DSN is not set. Example: export POSTGRES_DSN=postgresql://core:core@postgres:5432/corememory"
  exit 1
fi

cd $(dirname "$0")
# Run alembic from repo root so script_location paths resolve
cd ..

alembic -c projects/core_memory/alembic.ini upgrade head
