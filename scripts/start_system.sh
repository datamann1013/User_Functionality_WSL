#!/bin/bash

# RuneCore Ecosystem - Ordered Startup Script
# This script starts the entire RuneCore system with proper phased initialization

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker/docker-compose.unified.yml"

echo "============================================================================"
echo "RuneCore Ecosystem - System Startup"
echo "============================================================================"

# Check for .env file
if [ ! -f "$PROJECT_ROOT/docker/.env" ]; then
    echo "ERROR: .env file not found"
    echo "Please copy docker/.env.sample to docker/.env and configure it"
    exit 1
fi

cd "$PROJECT_ROOT/docker"

# Phase 1: Start Core Primary
echo ""
echo "[Phase 1] Starting Core Primary..."
docker-compose -f docker-compose.unified.yml up -d core_primary

echo "Waiting for Core Primary to initialize (max 60s)..."
for i in {1..60}; do
    if docker-compose -f docker-compose.unified.yml exec -T core_primary curl -f -k https://localhost:11440/health &>/dev/null; then
        echo "✓ Core Primary is healthy"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "ERROR: Core Primary failed to start"
        exit 1
    fi
    sleep 1
    echo -n "."
done

# Phase 2: Start Core Secondary
echo ""
echo "[Phase 2] Starting Core Secondary..."
docker-compose -f docker-compose.unified.yml up -d core_secondary

echo "Waiting for Core Secondary to join cluster (max 30s)..."
sleep 30
echo "✓ Core Secondary started"

# Phase 3: Wait for certificate provisioning
echo ""
echo "[Phase 3] Waiting for certificate provisioning..."
for i in {1..60}; do
    if docker volume inspect runecore_certs &>/dev/null; then
        echo "✓ Certificates volume exists"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "WARNING: Certificates may not be ready"
    fi
    sleep 1
done

# Phase 4: Start Database Services
echo ""
echo "[Phase 4] Starting Database Services..."
docker-compose -f docker-compose.unified.yml up -d postgresql redis influxdb

echo "Waiting for databases to be healthy (max 60s)..."
sleep 10
for i in {1..50}; do
    if docker-compose -f docker-compose.unified.yml ps postgresql | grep -q "healthy"; then
        echo "✓ PostgreSQL is healthy"
        break
    fi
    if [ $i -eq 50 ]; then
        echo "WARNING: PostgreSQL may not be fully ready"
    fi
    sleep 1
done

# Phase 5: Start Memory API
echo ""
echo "[Phase 5] Starting Memory API..."
docker-compose -f docker-compose.unified.yml up -d core_memory_api

echo "Waiting for Memory API to register with Core (max 30s)..."
sleep 15
echo "✓ Memory API started"

# Phase 6: Start RuneGuard Services
echo ""
echo "[Phase 6] Starting RuneGuard Services..."
docker-compose -f docker-compose.unified.yml up -d runeguard_logger

echo "✓ RuneGuard Logger started"

# Phase 7: Start AI Services
echo ""
echo "[Phase 7] Starting AI Services..."
echo "Starting Ollama..."
docker-compose -f docker-compose.unified.yml up -d ollama

echo "Waiting for Ollama to be ready (max 30s)..."
sleep 15

echo "Starting Ollama Service Wrapper..."
docker-compose -f docker-compose.unified.yml up -d ollama_service

sleep 5

echo "Starting AI Backend..."
docker-compose -f docker-compose.unified.yml up -d ai_backend

sleep 10

echo "Starting AI Frontend..."
docker-compose -f docker-compose.unified.yml up -d ai_frontend

# Final status
echo ""
echo "============================================================================"
echo "RuneCore Ecosystem Startup Complete"
echo "============================================================================"
echo ""
echo "Service Status:"
docker-compose -f docker-compose.unified.yml ps

echo ""
echo "Access Points:"
echo "  - Core Primary:  https://localhost:11440"
echo "  - Core Secondary: https://localhost:11441"
echo "  - AI Frontend:    http://localhost:3000"
echo ""
echo "To view logs: docker-compose -f docker/docker-compose.unified.yml logs -f [service_name]"
echo "To stop all:  docker-compose -f docker/docker-compose.unified.yml down"
echo ""
