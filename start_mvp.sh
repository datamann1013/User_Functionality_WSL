#!/bin/bash
# AI Service MVP Startup Script
# Minimal viable product with robust error handling

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_PATH="$PROJECT_ROOT/venv"
ERRORLOGGER_DIR="$PROJECT_ROOT/projects/ErrorLogger"
BACKEND_DIR="$PROJECT_ROOT/projects/ai_service/backend"

# Ports
ERRORLOGGER_PORT=5001
BACKEND_PORT=5000

# PID tracking
PIDS_FILE="$PROJECT_ROOT/.mvp_pids"

print_status() { echo -e "${BLUE}[MVP]${NC} $1"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Kill any existing processes on our ports
cleanup_ports() {
    print_status "Cleaning up existing processes..."
    
    for port in $ERRORLOGGER_PORT $BACKEND_PORT; do
        local pids=$(lsof -ti:$port 2>/dev/null || true)
        if [ ! -z "$pids" ]; then
            print_warning "Killing existing processes on port $port"
            echo "$pids" | xargs -r kill -9 2>/dev/null || true
            sleep 1
        fi
    done
}

check_port() {
    local port=$1
    # Simple port check using ss command
    if ss -tuln 2>/dev/null | grep -q ":$port "; then
        return 0  # Port is listening
    else
        return 1  # Port is not available
    fi
}

wait_for_service() {
    local port=$1
    local name=$2
    local max_attempts=30
    local attempt=0
    
    print_status "Waiting for $name to start on port $port..."
    
    while [ $attempt -lt $max_attempts ]; do
        if check_port $port; then
            print_success "$name is ready!"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
        echo -n "."
    done
    
    echo ""
    print_error "$name failed to start within $max_attempts seconds"
    return 1
}

check_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        print_error "Virtual environment not found at $VENV_PATH"
        print_status "Run ./install.sh first to set up the environment"
        exit 1
    fi
}

start_errorlogger() {
    print_status "Starting ErrorLogger MVP..."
    cd "$ERRORLOGGER_DIR"
    
    # Activate venv and start ErrorLogger
    source "$VENV_PATH/bin/activate"
    python errorlogger_mvp.py --debug > errorlogger_mvp.log 2>&1 &
    local pid=$!
    echo "errorlogger:$pid" >> "$PIDS_FILE"
    
    if wait_for_service $ERRORLOGGER_PORT "ErrorLogger"; then
        print_success "ErrorLogger MVP started (PID: $pid)"
        return 0
    else
        print_error "ErrorLogger MVP failed to start"
        print_status "Check errorlogger_mvp.log for details"
        cat errorlogger_mvp.log | tail -10
        return 1
    fi
}

start_backend() {
    print_status "Starting AI Backend MVP..."
    cd "$BACKEND_DIR"
    
    # Activate venv and start backend
    source "$VENV_PATH/bin/activate"
    python ai_backend_mvp.py --debug > ai_backend_mvp.log 2>&1 &
    local pid=$!
    echo "backend:$pid" >> "$PIDS_FILE"
    
    if wait_for_service $BACKEND_PORT "AI Backend"; then
        print_success "AI Backend MVP started (PID: $pid)"
        return 0
    else
        print_error "AI Backend MVP failed to start"
        print_status "Check ai_backend_mvp.log for details"
        cat ai_backend_mvp.log | tail -10
        return 1
    fi
}

stop_services() {
    print_status "Stopping MVP services..."
    
    if [ -f "$PIDS_FILE" ]; then
        while IFS=':' read -r service pid; do
            if [ ! -z "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                print_status "Stopping $service (PID: $pid)"
                kill "$pid" 2>/dev/null || true
            fi
        done < "$PIDS_FILE"
        rm -f "$PIDS_FILE"
    fi
    
    cleanup_ports
    print_success "All MVP services stopped"
}

show_status() {
    print_status "MVP Service Status:"
    echo "==================="
    
    echo -n "ErrorLogger MVP (port $ERRORLOGGER_PORT): "
    if check_port $ERRORLOGGER_PORT; then
        echo -e "${GREEN}RUNNING${NC}"
    else
        echo -e "${RED}STOPPED${NC}"
    fi
    
    echo -n "Backend MVP (port $BACKEND_PORT): "
    if check_port $BACKEND_PORT; then
        echo -e "${GREEN}RUNNING${NC}"
    else
        echo -e "${RED}STOPPED${NC}"
    fi
    
    echo ""
    echo "URLs:"
    echo "  Backend API: http://localhost:$BACKEND_PORT"
    echo "  Backend Web UI: http://localhost:$BACKEND_PORT"
    echo "  ErrorLogger: http://localhost:$ERRORLOGGER_PORT"
    echo "  Static Frontend: file://$(realpath $PROJECT_ROOT/projects/ai_service/frontend/chat_mvp.html)"
}

test_services() {
    print_status "Testing MVP services..."
    
    # Test ErrorLogger
    if check_port $ERRORLOGGER_PORT; then
        if curl -s http://localhost:$ERRORLOGGER_PORT/health >/dev/null; then
            print_success "ErrorLogger health check passed"
        else
            print_warning "ErrorLogger port open but health check failed"
        fi
    else
        print_error "ErrorLogger not responding"
    fi
    
    # Test Backend
    if check_port $BACKEND_PORT; then
        if curl -s http://localhost:$BACKEND_PORT/health >/dev/null; then
            print_success "Backend health check passed"
        else
            print_warning "Backend port open but health check failed"
        fi
    else
        print_error "Backend not responding"
    fi
}

start_mvp() {
    print_status "🚀 Starting AI Service MVP"
    print_status "=========================="
    
    # Prerequisites
    check_venv
    cleanup_ports
    
    # Initialize tracking
    rm -f "$PIDS_FILE"
    touch "$PIDS_FILE"
    
    # Start services
    if start_errorlogger; then
        sleep 2  # Give ErrorLogger time to initialize
        
        if start_backend; then
            sleep 3  # Give Backend time to initialize
            
            echo ""
            print_success "🎉 AI Service MVP started successfully!"
            echo ""
            show_status
            
            echo ""
            print_status "💡 Quick Test:"
            echo "  1. Open: http://localhost:$BACKEND_PORT"
            echo "  2. Or open: projects/ai_service/frontend/chat_mvp.html"
            echo "  3. Try chatting with the AI assistant"
            echo ""
            print_status "Press Ctrl+C to stop all services"
            
            # Monitor services
            trap 'stop_services; exit 0' INT TERM
            
            while true; do
                sleep 10
                # Basic health monitoring
                if ! check_port $ERRORLOGGER_PORT || ! check_port $BACKEND_PORT; then
                    print_warning "Service health check failed, attempting restart..."
                    break
                fi
            done
        else
            stop_services
            exit 1
        fi
    else
        stop_services
        exit 1
    fi
}

# Main script logic
case "${1:-start}" in
    "start")
        start_mvp
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        stop_services
        sleep 2
        start_mvp
        ;;
    "status")
        show_status
        ;;
    "test")
        test_services
        ;;
    "logs")
        echo "=== ErrorLogger Log ==="
        tail -20 "$ERRORLOGGER_DIR/errorlogger_mvp.log" 2>/dev/null || echo "No log file found"
        echo ""
        echo "=== Backend Log ==="
        tail -20 "$BACKEND_DIR/ai_backend_mvp.log" 2>/dev/null || echo "No log file found"
        ;;
    "help"|"-h"|"--help")
        echo "AI Service MVP Startup Script"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start     Start MVP services (default)"
        echo "  stop      Stop all services"
        echo "  restart   Restart all services"
        echo "  status    Show service status"
        echo "  test      Test service connectivity"
        echo "  logs      Show recent log output"
        echo "  help      Show this help"
        echo ""
        echo "MVP Features:"
        echo "  ✅ Lightweight services (no large model downloads)"
        echo "  ✅ Mock AI responses for testing"
        echo "  ✅ Full error logging integration"
        echo "  ✅ Web interface for testing"
        echo "  ✅ Discord-like chat UI"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
