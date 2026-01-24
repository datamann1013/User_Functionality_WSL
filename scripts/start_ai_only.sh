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

# Build and start AI services
echo "Building and starting AI services (this may take a moment)..."
docker compose -f docker-compose.dev.yml up -d --build

# Wait for services to be healthy
echo ""
echo "Waiting for services to become healthy..."
sleep 5

# Check health
echo ""
echo "Service Status:"
docker ps --filter "name=runecore_ai" --filter "name=runecore-ollama" --format "table {{.Names}}\t{{.Status}}"

# Test backend connectivity
echo ""
echo "Testing backend connectivity..."
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    echo "✅ Backend is healthy"
else
    echo "❌ Backend is not responding"
    echo "   Check logs: docker logs runecore_ai-backend-1"
fi

# Test frontend
echo "Testing frontend..."
if curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo "✅ Frontend is accessible"
else
    echo "❌ Frontend is not responding"
    echo "   Check logs: docker logs runecore_ai-frontend-1"
fi

# Test Ollama
echo "Testing Ollama wrapper..."
if curl -s http://localhost:5002/health > /dev/null 2>&1; then
    echo "✅ Ollama wrapper is healthy"
else
    echo "❌ Ollama wrapper is not responding"
    echo "   Check logs: docker logs runecore-ollama-wrapper"
fi

echo ""
echo "✅ AI Service started successfully!"
echo ""
echo "Access points:"
echo "  Frontend: http://localhost:3000"
echo "  Backend API: http://localhost:5000"
echo "  Backend Health: http://localhost:5000/health"
echo "  Ollama Wrapper: http://localhost:5002"
echo ""
echo "Running in STANDALONE mode with fallback memory (last 10 messages)"
echo "For persistent memory, start RuneCore_Memory service separately"
echo ""
echo "Useful commands:"
echo "  View backend logs: docker logs -f runecore_ai-backend-1"
echo "  View frontend logs: docker logs -f runecore_ai-frontend-1"
echo "  View ollama logs: docker logs -f runecore-ollama-wrapper"
echo "  Stop services: docker compose -f projects/RuneCore_AI/docker-compose.dev.yml down"
