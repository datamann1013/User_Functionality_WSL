#!/bin/bash
# AI Service Startup Script (Modular Architecture)
# Connects to existing ErrorLogger service

set -e

# Configuration
AI_SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$AI_SERVICE_DIR/../.." && pwd)"
BACKEND_DIR="$AI_SERVICE_DIR/backend"
VENV_DIR="$PROJECT_ROOT/venv"

# Service URLs
ERRORLOGGER_URL="http://127.0.0.1:5001"
AI_SERVICE_URL="http://127.0.0.1:5000"

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

# Check if service is running
check_service() {
    local url="$1"
    local name="$2"
    
    if curl -s "$url/health" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Wait for service to be ready
wait_for_service() {
    local url="$1"
    local name="$2"
    local timeout="${3:-30}"
    
    log_info "Waiting for $name to be ready..."
    
    for i in $(seq 1 $timeout); do
        if check_service "$url" "$name"; then
            log_success "$name is ready!"
            return 0
        fi
        sleep 1
    done
    
    log_error "$name failed to start within $timeout seconds"
    return 1
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    if [[ -n "${AI_PID:-}" ]]; then
        kill $AI_PID 2>/dev/null || true
        log_info "Stopped AI Service (PID: $AI_PID)"
    fi
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Main startup function
main() {
    log_info "🚀 Starting AI Service (Modular Architecture)"
    echo
    
    # Check if ErrorLogger is running
    if check_service "$ERRORLOGGER_URL" "ErrorLogger"; then
        log_success "✅ ErrorLogger service is running"
    else
        log_warning "⚠️  ErrorLogger service not found"
        log_info "To start ErrorLogger service:"
        log_info "cd $PROJECT_ROOT/projects/ErrorLogger && python error_logger_service.py --port 5001"
        log_info "AI Service will run without centralized logging"
    fi
    
    # Check if virtual environment exists
    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "Virtual environment not found at: $VENV_DIR"
        log_info "Please run: python -m venv $VENV_DIR"
        exit 1
    fi
    
    # Activate virtual environment
    log_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    
    # Check if AI service is already running
    if check_service "$AI_SERVICE_URL" "AI Service"; then
        log_error "AI Service is already running on port 5000"
        log_info "Stop it first or use a different port"
        exit 1
    fi
    
    # Install/update dependencies
    log_info "Checking dependencies..."
    pip install -q -r "$BACKEND_DIR/requirements.txt"
    
    # Set environment variables
    export ERRORLOGGER_SERVICE_URL="$ERRORLOGGER_URL/log"
    export FLASK_ENV="development"
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    
    # Start AI Service
    log_info "Starting AI Service backend..."
    cd "$BACKEND_DIR"
    
    # Start the service in background
    python app.py --port 5000 --host 127.0.0.1 &
    AI_PID=$!
    
    # Wait for service to be ready
    if wait_for_service "$AI_SERVICE_URL" "AI Service" 30; then
        echo
        log_success "🎉 AI Service is running!"
        echo
        log_info "Service Information:"
        log_info "  AI Service:    $AI_SERVICE_URL"
        log_info "  Health Check:  $AI_SERVICE_URL/health"
        log_info "  Models API:    $AI_SERVICE_URL/api/models"
        log_info "  Chat API:      $AI_SERVICE_URL/api/chat"
        log_info "  Inference API: $AI_SERVICE_URL/api/inference"
        
        if check_service "$ERRORLOGGER_URL" "ErrorLogger"; then
            log_info "  ErrorLogger:   $ERRORLOGGER_URL"
        fi
        
        echo
        log_info "Test the service:"
        log_info "  curl $AI_SERVICE_URL/health"
        log_info "  curl -X POST $AI_SERVICE_URL/api/chat -H 'Content-Type: application/json' -d '{\"message\":\"Hello!\"}'"
        echo
        
        # Keep running until interrupted
        log_info "Press Ctrl+C to stop..."
        wait $AI_PID
    else
        log_error "Failed to start AI Service"
        exit 1
    fi
}

# Run main function
main "$@"
