#!/bin/bash
# Test script to verify Ollama installation check

# Source the functions from the main script
AI_SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$AI_SERVICE_DIR/start_ai_service.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "🧪 Testing Ollama installation check..."
echo "======================================"

# Test the check function
check_and_install_ollama

echo ""
echo "✅ Test completed!"
