#!/bin/bash
# Demo of the new user-friendly messages

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

echo "🎬 Demo: What users see when Ollama is not installed"
echo "===================================================="
echo ""

log_info "🔍 Checking Ollama installation..."
log_error "❌ Ollama not installed!"
log_info ""
log_info "🔧 To install Ollama, please run this script with sudo:"
log_info "   sudo ./start_ai_service.sh"
log_info ""
log_info "Or install manually:"
log_info "   curl -fsSL https://ollama.ai/install.sh | sh"
log_info ""
log_warning "⚠️  Continuing without Ollama - AI will use demo mode only"

echo ""
echo "🎬 Demo: What happens when user runs with sudo"
echo "=============================================="
echo ""

echo "🔧 Installing Ollama (running as root)..."
echo "✅ Ollama installation complete!"
echo ""
echo "🚀 Please run this script again as a regular user:"
echo "   ./start_ai_service.sh"

echo ""
echo "✅ Demo completed!"
