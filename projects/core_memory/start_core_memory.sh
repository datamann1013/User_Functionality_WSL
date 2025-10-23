#!/usr/bin/env bash
set -euo pipefail
echo "Starting CoreMemory dev stack via docker-compose (optional)..."
if [ -f docker-compose.dev.yml ]; then
  docker-compose -f docker-compose.dev.yml up --build -d
else
  echo "No docker-compose.dev.yml found. You can run uvicorn directly:"
  echo "  uvicorn core_memory.app:app --host 0.0.0.0 --port 5010"
fi
