#!/bin/bash

# RuneCore Ecosystem - System Startup
# Starts all modules in dependency order using per-module docker-compose.dev.yml files.
#
# Startup order:
#   0. Pre-flight: stop stray containers on managed ports, start RuneSentry
#   1. Docker networks
#   2. RuneCore Core (Raft primary, PKI, service registry)
#   3. RuneCore HA   (Raft node 3, heartbeat offload)
#   4. RuneCore Memory (postgres, redis, influxdb, core_memory API)
#   5. RuneGuard Logger
#   6. RuneGuard Insight + RuneGuard Dashboard
#   7. RuneCore AI   (ollama, ollama_wrapper, backend, frontend)
#   8. RuneMesh Drop

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# ---- paths ---------------------------------------------------------------
CORE_DIR="$ROOT/projects/RuneCore_Core"
HA_DIR="$ROOT/projects/RuneCore_HA"
MEM_DIR="$ROOT/projects/RuneCore_Memory"
LOG_DIR="$ROOT/projects/RuneGuard_Logger"
INS_DIR="$ROOT/projects/RuneGuard_Insight"
DASH_DIR="$ROOT/projects/RuneGuard_Dashboard"
AI_DIR="$ROOT/projects/RuneCore_AI"
DROP_DIR="$ROOT/projects/RuneMesh_Drop"

# ---- helpers -------------------------------------------------------------

# Print a section header
phase() { echo ""; echo "[Phase $1] $2"; }

# Wait for a service to reach (healthy) status in its compose output.
# Usage: wait_healthy LABEL COMPOSE_FILE SERVICE [MAX_SECONDS]
wait_healthy() {
    local label="$1" file="$2" svc="$3" max="${4:-60}"
    echo -n "  Waiting for $label to be healthy (max ${max}s) ..."
    for ((i=1; i<=max; i++)); do
        out=$(docker compose -f "$file" ps "$svc" 2>/dev/null)
        if echo "$out" | grep -q "(healthy)"; then
            echo " ✓"
            return 0
        fi
        if echo "$out" | grep -q "(unhealthy)"; then
            echo " ✗ unhealthy — showing logs:"
            docker compose -f "$file" logs --tail=30 "$svc" 2>/dev/null || true
            return 1
        fi
        echo -n "."
        sleep 1
    done
    echo " (timed out — proceeding anyway)"
    return 0
}

# Bring up a module and show a one-liner result.
up() {
    local label="$1" file="$2"
    shift 2
    echo -n "  Starting $label ..."
    docker compose -f "$file" up -d "$@" 2>&1 | grep -E "(error|Error|ERRO)" || true
    echo " done"
}

# ---- pre-flight ----------------------------------------------------------
echo "============================================================================"
echo "RuneCore Ecosystem - System Startup"
echo "============================================================================"

# Stop any containers occupying ports that belong to the per-module setup but
# were left behind by a different compose project (e.g. the unified compose).
# Expected per-module container names (prefix-matched):
MANAGED_PORTS=(11440 11441 11442 5000 5001 5002 5004 5010 5100)
OWNED_CONTAINERS=("runecore_core-" "runecore_ha-" "runecore_memory-" "runeguard_logger-" "runeguard_dashboard-" "runeguard_insight-" "runecore_ai-" "runemesh_drop-" "runecore-ollama" "mesh_drop" "dashboard_backend" "runeguard_insight")

echo ""
echo "[Pre-flight] Checking for stray containers on managed ports..."
stray_found=false
for port in "${MANAGED_PORTS[@]}"; do
    # Find containers bound to this host port
    container=$(docker ps --format '{{.Names}} {{.Ports}}' 2>/dev/null \
        | grep "0\.0\.0\.0:${port}->" | awk '{print $1}' | head -1)
    if [ -z "$container" ]; then continue; fi

    # Check if it belongs to our managed set
    owned=false
    for owned_prefix in "${OWNED_CONTAINERS[@]}"; do
        if [[ "$container" == ${owned_prefix}* ]]; then
            owned=true; break
        fi
    done

    if [ "$owned" = false ]; then
        echo "  Stopping stray container on port $port: $container"
        docker stop "$container" &>/dev/null && docker rm "$container" &>/dev/null || true
        stray_found=true
    fi
done
[ "$stray_found" = false ] && echo "  No stray containers found."

# Start RuneSentry (native telemetry daemon) if not already running.
# RuneSentry feeds host_metrics and machine_profile to CoreMemory,
# which powers the Dashboard host/load panels and AI hardware detection.
echo ""
echo "[Pre-flight] RuneSentry (host telemetry daemon)..."
if tasklist.exe 2>/dev/null | grep -qi "RuneSentry"; then
    echo "  RuneSentry already running."
elif command -v RuneSentry.exe &>/dev/null; then
    powershell.exe -NoProfile -Command \
        "Start-Process -FilePath 'RuneSentry.exe' -WindowStyle Hidden" 2>/dev/null || true
    sleep 2
    if tasklist.exe 2>/dev/null | grep -qi "RuneSentry"; then
        echo "  ✓ RuneSentry started."
    else
        echo "  ⚠ RuneSentry may not have started — check manually."
    fi
else
    echo "  ⚠ RuneSentry not found in PATH — host telemetry will be unavailable."
    echo "    Build and install it: cd projects/RuneCore_Sentinel && ./manage.sh -ic"
fi

# ---- networks ------------------------------------------------------------
echo ""
echo "[Networks] Ensuring shared Docker networks exist..."
for net in runecore_dev runecore_ai_net runecore_memory_net; do
    docker network create "$net" 2>/dev/null \
        && echo "  Created:        $net" \
        || echo "  Already exists: $net"
done

# ---- Phase 1: Core -------------------------------------------------------
phase 1 "RuneCore Core (Raft primary, PKI, proxy)"
up "Core" "$CORE_DIR/docker-compose.dev.yml"
wait_healthy "Core" "$CORE_DIR/docker-compose.dev.yml" core 90

# ---- Phase 2: HA ---------------------------------------------------------
phase 2 "RuneCore HA (Raft node 3)"
# HA uses the image built in Phase 1 (runecore_core-core:latest). If not yet
# present, build it from the Core project first.
if ! docker image inspect runecore_core-core:latest &>/dev/null 2>&1; then
    echo "  Building Core image for HA node..."
    docker compose -f "$CORE_DIR/docker-compose.dev.yml" build core 2>&1 | tail -3
fi
up "HA" "$HA_DIR/docker-compose.dev.yml"
sleep 5
echo "  ✓ HA node started"

# ---- Phase 3: Memory -----------------------------------------------------
phase 3 "RuneCore Memory (postgres, redis, influxdb, core_memory API)"
up "Memory" "$MEM_DIR/docker-compose.dev.yml"
# Databases need time before core_memory starts connecting.
echo "  Waiting for databases (30s)..."
sleep 30
wait_healthy "PostgreSQL"  "$MEM_DIR/docker-compose.dev.yml" postgres  30
wait_healthy "Redis"       "$MEM_DIR/docker-compose.dev.yml" redis     30
wait_healthy "InfluxDB"    "$MEM_DIR/docker-compose.dev.yml" influx    60
wait_healthy "CoreMemory"  "$MEM_DIR/docker-compose.dev.yml" core_memory 60

# ---- Phase 4: RuneGuard Logger -------------------------------------------
phase 4 "RuneGuard Logger"
up "Logger" "$LOG_DIR/docker-compose.dev.yml"
wait_healthy "Logger" "$LOG_DIR/docker-compose.dev.yml" runeguard 30

# ---- Phase 5: RuneGuard Insight + Dashboard ------------------------------
phase 5 "RuneGuard Insight + Dashboard"
up "Insight"   "$INS_DIR/docker-compose.dev.yml"
up "Dashboard" "$DASH_DIR/docker-compose.dev.yml"
sleep 3
echo "  ✓ Insight and Dashboard started"

# ---- Phase 6: RuneCore AI ------------------------------------------------
phase 6 "RuneCore AI (Ollama, wrapper, backend, frontend)"
up "AI" "$AI_DIR/docker-compose.dev.yml"
# Ollama needs time to initialise before the wrapper and backend register.
echo "  Waiting for Ollama wrapper to be ready (30s)..."
sleep 30
wait_healthy "Ollama wrapper" "$AI_DIR/docker-compose.dev.yml" ollama_wrapper 60
wait_healthy "AI backend"     "$AI_DIR/docker-compose.dev.yml" backend        60
wait_healthy "AI frontend"    "$AI_DIR/docker-compose.dev.yml" frontend       60

# ---- Phase 7: RuneMesh Drop ----------------------------------------------
phase 7 "RuneMesh Drop"
up "Drop" "$DROP_DIR/docker-compose.dev.yml"
sleep 2
echo "  ✓ Drop started"

# ---- Summary -------------------------------------------------------------
echo ""
echo "============================================================================"
echo "RuneCore Ecosystem Startup Complete"
echo "============================================================================"
echo ""
echo "Running containers:"
docker ps --format "  {{.Names}}\t{{.Status}}" | sort
echo ""
echo "Access Points:"
echo "  Core (HTTPS):   https://localhost:11440"
echo "  Core HA:        https://localhost:11442"
echo "  CoreMemory:     http://localhost:5010"
echo "  RuneGuard:      http://localhost:5001"
echo "  Dashboard:      http://localhost:5004"
echo "  AI Frontend:    http://localhost:3000"
echo "  AI Backend:     http://localhost:5000"
echo "  Ollama Wrapper: http://localhost:5002"
echo "  RuneMesh Drop:  http://localhost:5100"
echo ""
echo "Native services (Windows host):"
if tasklist.exe 2>/dev/null | grep -qi "RuneSentry"; then
    echo "  RuneSentry: running  (host telemetry → CoreMemory)"
else
    echo "  RuneSentry: NOT running  (start: cd projects/RuneCore_Sentinel && ./manage.sh -r)"
fi
echo ""
echo "Logs:    docker compose -f projects/<module>/docker-compose.dev.yml logs -f"
echo "Stop:    ./scripts/stop_system.sh"
echo ""
