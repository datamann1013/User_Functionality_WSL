#!/bin/bash

# RuneCore Ecosystem - System Shutdown
# Stops all modules in reverse dependency order.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

CORE_DIR="$ROOT/projects/RuneCore_Core"
HA_DIR="$ROOT/projects/RuneCore_HA"
MEM_DIR="$ROOT/projects/RuneCore_Memory"
LOG_DIR="$ROOT/projects/RuneGuard_Logger"
INS_DIR="$ROOT/projects/RuneGuard_Insight"
DASH_DIR="$ROOT/projects/RuneGuard_Dashboard"
AI_DIR="$ROOT/projects/RuneCore_AI"
DROP_DIR="$ROOT/projects/RuneMesh_Drop"

echo "============================================================================"
echo "RuneCore Ecosystem - System Shutdown"
echo "============================================================================"

down() {
    local label="$1" file="$2"
    echo -n "  Stopping $label ..."
    docker compose -f "$file" down 2>&1 | grep -E "(error|Error|Removed)" || true
    echo " done"
}

down "RuneMesh Drop"       "$DROP_DIR/docker-compose.dev.yml"
down "RuneCore AI"         "$AI_DIR/docker-compose.dev.yml"
down "RuneGuard Dashboard" "$DASH_DIR/docker-compose.dev.yml"
down "RuneGuard Insight"   "$INS_DIR/docker-compose.dev.yml"
down "RuneGuard Logger"    "$LOG_DIR/docker-compose.dev.yml"
down "RuneCore Memory"     "$MEM_DIR/docker-compose.dev.yml"
down "RuneCore HA"         "$HA_DIR/docker-compose.dev.yml"
down "RuneCore Core"       "$CORE_DIR/docker-compose.dev.yml"

echo ""
echo "All services stopped."
echo ""
