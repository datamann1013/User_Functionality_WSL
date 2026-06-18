#!/usr/bin/env bash
set -euo pipefail

# Run alembic migrations using POSTGRES_DSN env var
if [ -z "${POSTGRES_DSN:-}" ]; then
  echo "POSTGRES_DSN is not set. Example: export POSTGRES_DSN=postgresql://core:core@postgres:5432/corememory"
  exit 1
fi

# Run from the directory that holds alembic.ini / the core_memory package.
# This is /app in the container and projects/RuneCore_Memory/ when run from a checkout.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Make the local core_memory package importable by alembic/env.py regardless of CWD.
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

alembic -c "$SCRIPT_DIR/alembic.ini" upgrade head
