#!/usr/bin/env bash
# Wrapper to bring down compose stacks discovered by start_all_with_compose.sh
# Usage: ./stop_all_with_compose.sh [filters...]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${SCRIPT_DIR}/.."
cd "${ROOT_DIR}"

# Forward to start_all_with_compose.sh with action 'down'
exec "${SCRIPT_DIR}/start_all_with_compose.sh" down "$@"
