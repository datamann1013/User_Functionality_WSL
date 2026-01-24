#!/usr/bin/env bash
# Stop only the AI service components

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🛑 Stopping RuneCore AI Service"
echo "================================"

cd "$REPO_ROOT/projects/RuneCore_AI"

docker compose -f docker-compose.dev.yml down

echo ""
echo "✅ AI Service stopped"
