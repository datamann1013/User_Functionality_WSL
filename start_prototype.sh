#!/bin/bash
# AI Service Startup Script
# Starts 3 separate servers: ErrorLogger + Backend + Frontend

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_DIR="$PROJECT_ROOT/venv"

# Service ports (configurable for different machines)
ERRORLOGGER_PORT=${ERRORLOGGER_PORT:-5001}
BACKEND_PORT=${BACKEND_PORT:-5000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}

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

# Check if service is running
check_service() {
    local url="$1"
    curl -s "$url/health" >/dev/null 2>&1
}

# Cleanup function
cleanup() {
    log_info "Shutting down all services..."
    
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
    
    if [[ -n "${FRONTEND_PID:-}" ]]; then
        kill $FRONTEND_PID 2>/dev/null || true
        log_info "Stopped Frontend service"
    fi
}

trap cleanup EXIT INT TERM

# Start ErrorLogger Server
start_errorlogger() {
    log_info "🔧 Starting ErrorLogger Server (Port: $ERRORLOGGER_PORT)"
    cd "$PROJECT_ROOT/projects/ErrorLogger"
    
    if check_service "http://127.0.0.1:$ERRORLOGGER_PORT"; then
        log_warning "ErrorLogger already running on port $ERRORLOGGER_PORT"
        return 0
    fi
    
    source "$VENV_DIR/bin/activate"
    python error_logger_service.py --port $ERRORLOGGER_PORT --host 127.0.0.1 > errorlogger.log 2>&1 &
    ERRORLOGGER_PID=$!
    echo $ERRORLOGGER_PID > errorlogger.pid
    
    # Wait for service to start
    sleep 2
    if check_service "http://127.0.0.1:$ERRORLOGGER_PORT"; then
        log_success "✅ ErrorLogger Server running (PID: $ERRORLOGGER_PID)"
        return 0
    else
        log_error "❌ ErrorLogger Server failed to start"
        return 1
    fi
}

# Start Backend Server
start_backend() {
    log_info "🤖 Starting Backend Server (Port: $BACKEND_PORT)"
    cd "$PROJECT_ROOT/projects/ai_service/backend"
    
    if check_service "http://127.0.0.1:$BACKEND_PORT"; then
        log_warning "Backend already running on port $BACKEND_PORT"
        return 0
    fi
    
    source "$VENV_DIR/bin/activate"
    pip install -q -r requirements.txt
    
    # Set environment for backend
    export ERRORLOGGER_SERVICE_URL="http://127.0.0.1:$ERRORLOGGER_PORT/log"
    
    python app.py --port $BACKEND_PORT --host 127.0.0.1 > backend.log 2>&1 &
    BACKEND_PID=$!
    
    # Wait for service to start
    sleep 3
    if check_service "http://127.0.0.1:$BACKEND_PORT"; then
        log_success "✅ Backend Server running (PID: $BACKEND_PID)"
        return 0
    else
        log_error "❌ Backend Server failed to start"
        return 1
    fi
}

# Start Frontend Server
start_frontend() {
    log_info "🌐 Starting Frontend Server (Port: $FRONTEND_PORT)"
    cd "$PROJECT_ROOT/projects/ai_service/frontend"
    
    # Install dependencies if needed
    if [[ ! -d "node_modules" ]]; then
        log_info "Installing npm dependencies..."
        npm install
    fi
    
    # Set environment for frontend
    export REACT_APP_BACKEND_URL="http://localhost:$BACKEND_PORT"
    export PORT=$FRONTEND_PORT
    
    npm start > frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    # Wait for service to start
    log_info "Waiting for React development server to start..."
    sleep 8
    
    if curl -s "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1; then
        log_success "✅ Frontend Server running (PID: $FRONTEND_PID)"
        return 0
    else
        log_warning "⚠️  Frontend may still be starting..."
        return 0
    fi
}

# Main function
main() {
    echo "🚀 AI Service - Three Server Architecture"
    echo "   This will start 3 separate servers that can run independently:"
    echo "   📊 ErrorLogger Server  (Port: $ERRORLOGGER_PORT)"
    echo "   🤖 Backend Server      (Port: $BACKEND_PORT)" 
    echo "   🌐 Frontend Server     (Port: $FRONTEND_PORT)"
    echo

    # Check prerequisites
    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "Virtual environment not found at: $VENV_DIR"
        log_info "Please run: python -m venv $VENV_DIR"
        exit 1
    fi

    if ! command -v node >/dev/null 2>&1; then
        log_error "Node.js not found. Please install Node.js first."
        exit 1
    fi

    # Start services in sequence
    if ! start_errorlogger; then
        exit 1
    fi
    
    sleep 1
    
    if ! start_backend; then
        exit 1
    fi
    
    sleep 1
    
    if ! start_frontend; then
        exit 1
    fi

    echo
    log_success "🎉 All servers are running!"
    echo
    log_info "Access your services:"
    log_info "  🌐 Frontend:     http://localhost:$FRONTEND_PORT"
    log_info "  🤖 Backend API:  http://localhost:$BACKEND_PORT"
    log_info "  📊 ErrorLogger:  http://localhost:$ERRORLOGGER_PORT"
    echo
    log_info "Logs:"
    log_info "  ErrorLogger: projects/ErrorLogger/errorlogger.log"
    log_info "  Backend:     projects/ai_service/backend/backend.log"
    log_info "  Frontend:    projects/ai_service/frontend/frontend.log"
    echo
    log_info "🔧 To run on different machines, set environment variables:"
    log_info "   ERRORLOGGER_PORT=5001 BACKEND_PORT=5000 FRONTEND_PORT=3000"
    echo
    log_info "Press Ctrl+C to stop all services..."
    
    # Keep script running and show status
    while true; do
        sleep 10
        
        # Check if all services are still running
        all_running=true
        
        if ! check_service "http://127.0.0.1:$ERRORLOGGER_PORT"; then
            log_warning "⚠️  ErrorLogger service appears to be down"
            all_running=false
        fi
        
        if ! check_service "http://127.0.0.1:$BACKEND_PORT"; then
            log_warning "⚠️  Backend service appears to be down" 
            all_running=false
        fi
        
        if ! curl -s "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1; then
            log_warning "⚠️  Frontend service appears to be down"
            all_running=false
        fi
        
        if [[ $all_running == false ]]; then
            log_error "Some services are down. Check logs or restart."
            break
        fi
    done
}

# Run main function
main "$@"
