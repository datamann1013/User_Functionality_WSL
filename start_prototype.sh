#!/bin/bash
# AI Service Minimal Startup Script
# Starts ErrorLogger, Backend, and React Frontend

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
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

# Cleanup function
cleanup() {
    log_info "Cleaning up services..."
    
    # Kill background processes
    if [[ -f "$PROJECT_ROOT/projects/ErrorLogger/errorlogger.pid" ]]; then
        PID=$(cat "$PROJECT_ROOT/projects/ErrorLogger/errorlogger.pid" 2>/dev/null || echo "")
        if [[ -n "$PID" ]]; then
            kill $PID 2>/dev/null || true
            rm -f "$PROJECT_ROOT/projects/ErrorLogger/errorlogger.pid"
            log_info "Stopped ErrorLogger service"
        fi
    fi
    
    if [[ -n "${BACKEND_PID:-}" ]]; then
        kill $BACKEND_PID 2>/dev/null || true
        log_info "Stopped Backend service"
    fi
}

trap cleanup EXIT INT TERM

# Main function
main() {
    echo "🚀 Starting AI Service (Minimal Setup)"
    echo "   This will start: ErrorLogger + Backend + React Frontend"
    echo

    # Check virtual environment
    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "Virtual environment not found at: $VENV_DIR"
        log_info "Please run: python -m venv $VENV_DIR"
        exit 1
    fi

    # Check Node.js
    if ! command -v node >/dev/null 2>&1; then
        log_error "Node.js not found. Please install Node.js first."
        exit 1
    fi

    # Start ErrorLogger in background
    log_info "1. Starting ErrorLogger service..."
    cd "$PROJECT_ROOT/projects/ErrorLogger"
    source "$VENV_DIR/bin/activate"
    python error_logger_service.py --port 5001 --host 127.0.0.1 > errorlogger.log 2>&1 &
    ERRORLOGGER_PID=$!
    echo $ERRORLOGGER_PID > errorlogger.pid
    
    # Wait for ErrorLogger to be ready
    sleep 2
    if curl -s "http://127.0.0.1:5001/health" >/dev/null 2>&1; then
        log_success "✅ ErrorLogger service running (PID: $ERRORLOGGER_PID)"
    else
        log_warning "⚠️  ErrorLogger may not be ready"
    fi

    # Start Backend in background
    log_info "2. Starting AI Service backend..."
    cd "$PROJECT_ROOT/projects/ai_service/backend"
    source "$VENV_DIR/bin/activate"
    pip install -q -r requirements.txt
    python app.py --port 5000 --host 127.0.0.1 > backend.log 2>&1 &
    BACKEND_PID=$!
    
    # Wait for Backend to be ready
    sleep 3
    if curl -s "http://127.0.0.1:5000/health" >/dev/null 2>&1; then
        log_success "✅ Backend service running (PID: $BACKEND_PID)"
    else
        log_error "❌ Backend failed to start"
        exit 1
    fi

    # Start React Frontend
    log_info "3. Starting React frontend..."
    cd "$PROJECT_ROOT/projects/ai_service/frontend"
    
    # Install dependencies if needed
    if [[ ! -d "node_modules" ]]; then
        log_info "Installing npm dependencies..."
        npm install
    fi
    
    echo
    log_success "🎉 All services are running!"
    echo
    log_info "Service URLs:"
    log_info "  ErrorLogger:  http://127.0.0.1:5001"
    log_info "  Backend API:  http://127.0.0.1:5000"
    log_info "  Frontend:     http://127.0.0.1:3000"
    echo
    log_info "Starting React development server..."
    log_info "Press Ctrl+C to stop all services"
    echo
    
    # Start React dev server (this will block)
    REACT_APP_BACKEND_URL="http://localhost:5000" npm start
}

# Run main function
main "$@"
