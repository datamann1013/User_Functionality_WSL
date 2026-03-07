#!/usr/bin/env bash
# Start RuneMesh_Drop service
# This script builds and starts the RuneMesh_Drop container

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[RuneMesh_Drop] Starting File Transfer Service"
echo "=============================================="

# Ensure the runecore_dev network exists
if ! docker network inspect runecore_dev >/dev/null 2>&1; then
    echo "Creating runecore_dev network..."
    docker network create runecore_dev
fi

# Navigate to RuneMesh_Drop project directory
cd "$REPO_ROOT/projects/RuneMesh_Drop"

# Stop any existing RuneMesh_Drop container
echo "Stopping any existing RuneMesh_Drop container..."
docker compose -f docker-compose.dev.yml down 2>/dev/null || true

# Build and start RuneMesh_Drop
echo "Building and starting RuneMesh_Drop..."
docker compose -f docker-compose.dev.yml up -d --build

# Wait for container to spin up
echo "Waiting for service to start..."
sleep 3

# Check container status
echo ""
echo "Container Status:"
docker ps --filter "name=mesh_drop" --format "table {{.Names}}\t{{.Status}}"

# Test health endpoint
echo ""
echo "Testing service health..."
HEALTH_OK=0
for i in $(seq 1 10); do
    if curl -s --max-time 3 http://localhost:5100/health > /dev/null 2>&1; then
        echo "[OK] Service is healthy"
        HEALTH_OK=1
        break
    fi
    printf "   Waiting for service... (%ds)\r" "$((i * 2))"
    sleep 2
done

if [ $HEALTH_OK -eq 0 ]; then
    echo "[WARN] Service did not respond quickly. Check logs: docker logs mesh_drop"
else
    # Test frontend
    echo ""
    echo "Testing frontend..."
    if curl -s --max-time 5 http://localhost:5100/ > /dev/null 2>&1; then
        echo "[OK] Frontend is accessible"
    else
        echo "[WARN] Frontend may not be ready yet"
    fi
fi

echo ""
echo "[OK] RuneMesh_Drop started successfully!"
echo ""
echo "Access points:"
echo "  Frontend: http://localhost:5100"
echo "  Backend API: http://localhost:5100"
echo "  Health: http://localhost:5100/health"
echo "  Via Core Proxy: http://localhost:11441/api/proxy/RuneMesh_Drop/"
echo ""
echo "Useful commands:"
echo "  View logs: docker logs -f mesh_drop"
echo "  Stop: docker compose -f projects/RuneMesh_Drop/docker-compose.dev.yml down"
