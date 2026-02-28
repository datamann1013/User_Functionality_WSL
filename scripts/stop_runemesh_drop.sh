#!/usr/bin/env bash
# Stop RuneMesh_Drop service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[RuneMesh_Drop] Stopping File Transfer Service"

cd "$REPO_ROOT/projects/RuneMesh_Drop"

docker compose -f docker-compose.dev.yml down

echo "[OK] RuneMesh_Drop stopped"
