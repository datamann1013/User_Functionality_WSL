#!/bin/bash
# Test script to show what happens when Ollama is not installed

# Temporarily rename ollama to simulate it not being installed
if command -v ollama >/dev/null 2>&1; then
    echo "🧪 Testing: Simulating missing Ollama..."
    sudo mv /usr/local/bin/ollama /usr/local/bin/ollama.backup 2>/dev/null || echo "Ollama not in /usr/local/bin"
    sudo mv /usr/bin/ollama /usr/bin/ollama.backup 2>/dev/null || echo "Ollama not in /usr/bin"
fi

# Test the check function
echo ""
echo "Testing startup script behavior without Ollama:"
echo "=============================================="

# Source just the check function to test it
AI_SERVICE_DIR="/home/administrator/gitcontrol/User_Functionality_WSL/projects/ai_service"
PROJECT_ROOT="$(cd "$AI_SERVICE_DIR/../.." && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Inline version of the check function
check_and_install_ollama() {
    log_info "🔍 Checking Ollama installation..."
    
    if command -v ollama >/dev/null 2>&1; then
        log_success "✅ Ollama is already installed"
        return 0
    else
        log_error "❌ Ollama not installed!"
        log_info ""
        log_info "🔧 To install Ollama, please run this script with sudo:"
        log_info "   sudo ./start_ai_service.sh"
        log_info ""
        log_info "Or install manually:"
        log_info "   curl -fsSL https://ollama.ai/install.sh | sh"
        log_info ""
        log_warning "⚠️  Continuing without Ollama - AI will use demo mode only"
        return 1
    fi
}

# Run the test
check_and_install_ollama

echo ""
echo "🔄 Restoring Ollama..."

# Restore ollama
sudo mv /usr/local/bin/ollama.backup /usr/local/bin/ollama 2>/dev/null || echo "No backup in /usr/local/bin"
sudo mv /usr/bin/ollama.backup /usr/bin/ollama 2>/dev/null || echo "No backup in /usr/bin"

# Check if restoration worked
if command -v ollama >/dev/null 2>&1; then
    echo "✅ Ollama restored successfully"
else
    echo "⚠️  Could not restore Ollama - it may be in a different location"
fi

echo ""
echo "✅ Test completed!"
