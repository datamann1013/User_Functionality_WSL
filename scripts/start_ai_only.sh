#!/usr/bin/env bash
# Start only the AI service components (backend, frontend, ollama, ollama_wrapper)
# This script is for standalone AI development without Memory Core or other services

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🤖 Starting RuneCore AI Service (Standalone Mode)"
echo "================================================"

# Ensure the runecore_dev network exists
if ! docker network inspect runecore_dev >/dev/null 2>&1; then
    echo "Creating runecore_dev network..."
    docker network create runecore_dev
fi

# Navigate to AI project directory
cd "$REPO_ROOT/projects/RuneCore_AI"

# Stop any existing AI containers
echo "Stopping any existing AI containers..."
docker compose -f docker-compose.dev.yml down 2>/dev/null || true

# Start AI services
echo "Starting AI services..."
docker compose -f docker-compose.dev.yml up -d

# Wait for services to be healthy
echo ""
echo "Waiting for services to become healthy..."
sleep 3

# Check health
echo ""
echo "Service Status:"
docker ps --filter "name=runecore_ai" --filter "name=runecore-ollama" --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "✅ AI Service started successfully!"
echo ""
echo "Access points:"
echo "  Frontend: http://localhost:3000"
echo "  Backend API: http://localhost:5000"
echo "  Ollama Wrapper: http://localhost:5002"
echo ""
echo "Running in STANDALONE mode with fallback memory (last 10 messages)"
echo "For persistent memory, start RuneCore_Memory service separately"
