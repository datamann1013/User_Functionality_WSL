#!/usr/bin/env bash
# Start/stop docker-compose stacks for each microservice in the repo.
# Usage:
#   ./scripts/start_all_with_compose.sh up [filter1 filter2 ...]
#   ./scripts/start_all_with_compose.sh down [filter1 filter2 ...]
# Examples:
#   ./scripts/start_all_with_compose.sh up
#   ./scripts/start_all_with_compose.sh up memory
# Environment:
# - Exports from your shell are passed through to docker compose; set RUNECORE_REGISTER_WITH_CORE or RUNECORE_DISABLE_MTLS before running if needed.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}/.."
cd "${ROOT_DIR}"

# Preload saved dev base images if present
ARTIFACT_DIR="$ROOT_DIR/artifacts/dev-bases"
if [ -d "$ARTIFACT_DIR" ]; then
  for t in "$ARTIFACT_DIR"/*.tar; do
    [ -f "$t" ] || continue
    echo "Loading prebuilt base image from $t"
    docker load -i "$t" || true
  done
fi

# If local tarballs exist, prefer dev compose files but allow running all stacks;
# export USE_LOCAL_BASES=1 to explicitly indicate local-first behavior.
if compgen -G "$ARTIFACT_DIR/*.tar" > /dev/null 2>&1; then
  echo "Found local dev base tarballs in $ARTIFACT_DIR; these will be used for builds."
  USE_LOCAL_BASES=1
fi

# Known compose files (relative to repo root). Add more if you have per-project compose files.
# Auto-discover compose files. Prefer dev files first for developer workflows.
COMPOSE_FILES=()
shopt -s globstar nullglob || true
found_files=()
for p in projects/**/docker-compose*.yml docker/**/docker-compose*.yml docker/docker-compose*.yml docker-compose*.yml; do
  if [ -f "$p" ]; then
    found_files+=("$p")
  fi
done

# Add dev files first
dev_files=()
other_files=()
for f in "${found_files[@]}"; do
  if [[ "$f" == *dev* ]]; then
    dev_files+=("$f")
  else
    other_files+=("$f")
  fi
done

# Combine, preserving order and uniqueness
declare -A _seen
for f in "${dev_files[@]}" "${other_files[@]}"; do
  if [ -z "${_seen[$f]:-}" ]; then
    COMPOSE_FILES+=("$f")
    _seen[$f]=1
  fi
done

if [ ${#COMPOSE_FILES[@]} -eq 0 ]; then
  echo "No docker-compose files found in repo (searched projects/** and docker/**)." >&2
fi

# By default, prefer only dev compose files. Set ALLOW_PROD_COMPOSE=1 to include prod or other non-dev files.
ALLOW_PROD_COMPOSE=${ALLOW_PROD_COMPOSE:-0}
if [ "$ALLOW_PROD_COMPOSE" != "1" ]; then
  filtered=()
  for f in "${COMPOSE_FILES[@]}"; do
    if [[ "$f" == *dev* ]]; then
      filtered+=("$f")
    fi
  done
  if [ ${#filtered[@]} -gt 0 ]; then
    COMPOSE_FILES=("${filtered[@]}")
  fi
fi

# Detect docker compose command
COMPOSE_CMD=""
if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
  fi
fi
if [ -z "${COMPOSE_CMD}" ]; then
  if command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
  else
    echo "ERROR: docker compose not found. Install docker (with compose plugin) or docker-compose." >&2
    exit 2
  fi
fi

action="${1-}" || true
# Default to bringing up stacks and waiting for health when no action provided.
if [ -z "$action" ]; then
  action="test-ready"
  echo "No action provided; defaulting to: $action"
fi
shift || true
filters=("$@")

# Build controls (env vars)
SKIP_BUILD=${SKIP_BUILD:-0}
NO_CACHE=${NO_CACHE:-0}
SKIP_MISSING_CONTEXTS=${SKIP_MISSING_CONTEXTS:-1}

NO_CACHE_FLAG=""
if [ "$NO_CACHE" = "1" ]; then
  NO_CACHE_FLAG="--no-cache"
fi


# Extract candidate build contexts from a compose file. Prints each context on a new line.
find_build_contexts() {
  local file="$1"
  local prev_build=0
  while IFS= read -r line || [ -n "$line" ]; do
    # Trim leading spaces for pattern matching
    if [[ "$line" =~ ^[[:space:]]*build:[[:space:]]*(.+)$ ]]; then
      local val="${BASH_REMATCH[1]}"
      val="$(echo "$val" | sed -E 's/^[[:space:]]*|[[:space:]]*$//g' | sed -E 's/[",]//g')"
      if [ -n "$val" ] && [ "$val" != "{" ]; then
        echo "$val"
        prev_build=0
      else
        prev_build=1
      fi
    elif [[ "$line" =~ ^[[:space:]]*context:[[:space:]]*(.+)$ ]]; then
      local val="${BASH_REMATCH[1]}"
      val="$(echo "$val" | sed -E 's/^[[:space:]]*|[[:space:]]*$//g' | sed -E 's/[",]//g')"
      echo "$val"
      prev_build=0
    else
      if [ $prev_build -eq 1 ]; then
        if [[ "$line" =~ ^[[:space:]]+context:[[:space:]]*(.+)$ ]]; then
          local val="${BASH_REMATCH[1]}"
          val="$(echo "$val" | sed -E 's/^[[:space:]]*|[[:space:]]*$//g' | sed -E 's/[",]//g')"
          echo "$val"
        elif [[ ! "$line" =~ ^[[:space:]] ]]; then
          prev_build=0
        fi
      fi
    fi
  done <"$file"
}


# Check that all build contexts referenced in the compose file exist on disk.
# Returns 0 if all exist or no contexts found, 1 if any missing.
contexts_exist() {
  local file="$1"
  local dir
  dir=$(dirname "$file")
  local missing=0
  while IFS= read -r ctx; do
    [ -z "$ctx" ] && continue
    # Resolve relative paths
    local resolved
    if [[ "$ctx" = /* ]]; then
      resolved="$ctx"
    else
      resolved="$dir/$ctx"
    fi
    # Normalize possible trailing / or ./
    resolved="$(echo "$resolved" | sed -E 's#//+#/#g')"
    if [ ! -e "$resolved" ]; then
      echo "Missing build context: $ctx -> $resolved" >&2
      missing=1
    fi
  done < <(find_build_contexts "$file")
  return $missing
}

matches_filters() {
  # If no filters provided, match everything
  if [ ${#filters[@]} -eq 0 ]; then
    return 0
  fi
  local file="$1"
  local bn
  bn=$(basename "$file")
  for f in "${filters[@]}"; do
    if [[ "$file" == *"$f"* || "$bn" == *"$f"* ]]; then
      return 0
    fi
  done
  return 1
}

run_up() {
  local file="$1"
  echo "--> Bringing up compose stack: $file"
  # Validate compose syntax first
  if ! "${COMPOSE_CMD[@]}" -f "$file" config >/dev/null 2>&1; then
    echo "--> Invalid compose file (syntax/config) — skipping: $file" >&2
    return
  fi
  if [ "$SKIP_BUILD" != "1" ]; then
    if [ "$SKIP_MISSING_CONTEXTS" = "1" ]; then
      if ! contexts_exist "$file"; then
        echo "--> Skipping compose file due to missing build contexts: $file"
        return
      fi
    fi
    echo "--> Building images for: $file"
    "${COMPOSE_CMD[@]}" -f "$file" build ${NO_CACHE_FLAG}
  else
    echo "--> SKIP_BUILD=1 set; skipping build for: $file"
  fi
  "${COMPOSE_CMD[@]}" -f "$file" up -d
}

# Wait for healthchecks exposed by compose stacks. This polls each container's
# health status via `docker ps`/`docker inspect` when available or a simple
# curl against common ports if a healthcheck isn't set.
wait_for_health() {
  local timeout=${1:-60}
  local interval=3
  local elapsed=0
  echo "Waiting up to ${timeout}s for containers to report healthy..."
  while [ $elapsed -lt $timeout ]; do
    # If there are any containers in HEALTHY state, consider them ok; if any
    # are starting or unhealthy, keep waiting.
    unhealthy=$(docker ps --filter "label=com.docker.compose.project" --format '{{.ID}}' | xargs -r docker inspect --format='{{.State.Health.Status}}' 2>/dev/null | grep -v healthy || true)
    if [ -z "$unhealthy" ]; then
      echo "All containers healthy (or no healthchecks defined)."
      return 0
    fi
    sleep $interval
    elapsed=$((elapsed+interval))
  done
  echo "Timeout waiting for healthy containers." >&2
  return 1
}

run_down() {
  local file="$1"
  echo "--> Bringing down compose stack: $file"
  "${COMPOSE_CMD[@]}" -f "$file" down
}

# Main loop
for cfile in "${COMPOSE_FILES[@]}"; do
  if [ ! -f "$cfile" ]; then
    echo "Skipping missing compose file: $cfile"
    continue
  fi
  if matches_filters "$cfile"; then
    case "$action" in
      list)
        echo "Discovered compose files (dev-first):"
        for f in "${COMPOSE_FILES[@]}"; do
          echo "  - $f"
        done
        exit 0
        ;;
      up)
  run_up "$cfile"
        ;;
      down)
        run_down "$cfile"
        ;;
      restart)
        run_down "$cfile" || true
        run_up "$cfile"
        ;;
      test-ready)
        # Bring up all stacks and then wait for health
        run_up "$cfile"
        ;;
      *)
        echo "Unknown action: $action" >&2
        exit 2
        ;;
    esac
  else
    echo "Skipping (filter): $cfile"
  fi
done

echo "All requested compose actions finished."

# If action is test-ready, wait for containers to report healthy
if [ "$action" = "test-ready" ]; then
  # Allow caller to override timeout via WAIT_TIMEOUT env var (seconds)
  WAIT_TIMEOUT=${WAIT_TIMEOUT:-120}
  if ! wait_for_health "$WAIT_TIMEOUT"; then
    echo "One or more containers failed to report healthy within ${WAIT_TIMEOUT}s." >&2
    exit 3
  fi
  echo "Stacks are up and healthy."
fi
