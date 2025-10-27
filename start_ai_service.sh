#!/bin/bash
# AI Service Startup Script
# Automatically starts ErrorLogger, Backend, and Frontend services

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_PATH="$PROJECT_ROOT/venv"
ERRORLOGGER_DIR="$PROJECT_ROOT/projects/ErrorLogger"
BACKEND_DIR="$PROJECT_ROOT/projects/ai_service/backend"
FRONTEND_DIR="$PROJECT_ROOT/projects/ai_service/frontend"

# Default ports
ERRORLOGGER_PORT=5001
BACKEND_PORT=5000
FRONTEND_PORT=3000

# PIDs storage
PIDS_FILE="$PROJECT_ROOT/.service_pids"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[AI-SERVICE]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check if a port is in use
check_port() {
    local port=$1
    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to find process using a port
get_pid_by_port() {
    local port=$1
    lsof -ti:$port 2>/dev/null || echo ""
}

# Function to check if virtual environment exists
check_venv() {
    if [ ! -d "$VENV_PATH" ]; then
        print_error "Virtual environment not found at $VENV_PATH"
        print_status "Please run ./install.sh first to set up the environment"
        exit 1
    fi
}

# Function to activate virtual environment
activate_venv() {
    print_status "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
    print_success "Virtual environment activated"
}

# Function to check and start ErrorLogger
start_errorlogger() {
    print_status "Checking ErrorLogger service..."
    
    if check_port $ERRORLOGGER_PORT; then
        local pid=$(get_pid_by_port $ERRORLOGGER_PORT)
        print_warning "ErrorLogger already running on port $ERRORLOGGER_PORT (PID: $pid)"
        return 0
    fi
    
    print_status "Starting ErrorLogger service..."
    cd "$ERRORLOGGER_DIR"
    
    # Start ErrorLogger in background
    python error_server.py --debug > errorlogger.log 2>&1 &
    local errorlogger_pid=$!
    echo "errorlogger:$errorlogger_pid" >> "$PIDS_FILE"
    
    # Wait a moment for startup
    sleep 2
    
    # Check if it started successfully
    if check_port $ERRORLOGGER_PORT; then
        print_success "ErrorLogger started successfully (PID: $errorlogger_pid)"
    else
        print_error "Failed to start ErrorLogger"
        print_status "Check errorlogger.log for details"
        exit 1
    fi
}

# Function to start Backend
start_backend() {
    print_status "Starting AI Service Backend with Redis Cache..."
    cd "$BACKEND_DIR"
    
    if check_port $BACKEND_PORT; then
        local pid=$(get_pid_by_port $BACKEND_PORT)
        print_warning "Backend already running on port $BACKEND_PORT (PID: $pid)"
        return 0
    fi
    
    # Set Redis cache environment variables for local development
    export LOCAL_CACHE_ENABLED=true
    export LOCAL_CACHE_MESSAGE_LIMIT=10
    export LOCAL_CACHE_CONTEXT_SIZE=5
    export REDIS_HOST=localhost
    export REDIS_PORT=6379
    export REDIS_DB=0
    
    # Check if Redis is available locally
    print_status "Checking Redis availability..."
    if command -v redis-server >/dev/null 2>&1 && command -v redis-cli >/dev/null 2>&1; then
        # Check if Redis is already running
        if ! redis-cli ping >/dev/null 2>&1; then
            print_status "Starting local Redis server for conversation cache..."
            redis-server --daemonize yes --port 6379 --maxmemory 128mb --maxmemory-policy allkeys-lru --save "" >/dev/null 2>&1 &
            sleep 2
            
            if redis-cli ping >/dev/null 2>&1; then
                print_success "Redis server started for conversation cache"
            else
                print_warning "Redis failed to start - will use fallback Python dict cache"
            fi
        else
            print_success "Redis already running - using for conversation cache"
        fi
    else
        print_warning "Redis not found - will use fallback Python dict cache"
        print_status "  To install Redis: sudo apt-get install redis-server (Ubuntu/Debian)"
        print_status "  Or: brew install redis (macOS)"
    fi
    
    # Start backend (now with Redis cache support)
    python app.py > backend.log 2>&1 &
    local backend_pid=$!
    echo "backend:$backend_pid" >> "$PIDS_FILE"
    
    # Wait for backend to start
    print_status "Waiting for backend to initialize..."
    local attempts=0
    while [ $attempts -lt 30 ]; do
        if check_port $BACKEND_PORT; then
            print_success "Backend started successfully with conversation cache (PID: $backend_pid)"
            
            # Test cache functionality
            print_status "Testing conversation cache..."
            sleep 2
            if curl -s -f http://localhost:$BACKEND_PORT/api/cache/stats >/dev/null 2>&1; then
                print_success "Conversation cache is operational"
            else
                print_warning "Cache status endpoint not responding (may still be initializing)"
            fi
            return 0
        fi
        sleep 1
        attempts=$((attempts + 1))
    done
    
    print_error "Backend failed to start within 30 seconds"
    print_status "Check backend.log for details"
    exit 1
}

# Function to start Frontend
start_frontend() {
    print_status "Starting Frontend..."
    cd "$FRONTEND_DIR"
    
    if check_port $FRONTEND_PORT; then
        local pid=$(get_pid_by_port $FRONTEND_PORT)
        print_warning "Frontend already running on port $FRONTEND_PORT (PID: $pid)"
        return 0
    fi
    
    # Check if npm is available
    if ! command -v npm &> /dev/null; then
        print_error "npm not found. Please install Node.js to run the frontend."
        print_status "Backend services are running. You can access the API at http://localhost:$BACKEND_PORT"
        return 1
    fi
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        print_status "Installing frontend dependencies..."
        npm install
    fi
    
    # Start frontend
    print_status "Starting React development server..."
    npm start > frontend.log 2>&1 &
    local frontend_pid=$!
    echo "frontend:$frontend_pid" >> "$PIDS_FILE"
    
    # Wait for frontend to start
    print_status "Waiting for frontend to initialize..."
    local attempts=0
    while [ $attempts -lt 60 ]; do
        if check_port $FRONTEND_PORT; then
            print_success "Frontend started successfully (PID: $frontend_pid)"
            return 0
        fi
        sleep 2
        attempts=$((attempts + 1))
    done
    
    print_warning "Frontend may still be starting. Check frontend.log for details"
}

# Function to show service status
show_status() {
    print_status "Service Status:"
    echo "===================="
    
    echo -n "ErrorLogger (port $ERRORLOGGER_PORT): "
    if check_port $ERRORLOGGER_PORT; then
        echo -e "${GREEN}RUNNING${NC}"
    else
        echo -e "${RED}STOPPED${NC}"
    fi
    
    echo -n "Backend (port $BACKEND_PORT): "
    if check_port $BACKEND_PORT; then
        echo -e "${GREEN}RUNNING${NC}"
        
        # Check conversation cache status
        if curl -s -f http://localhost:$BACKEND_PORT/api/cache/stats >/dev/null 2>&1; then
            local cache_info=$(curl -s http://localhost:$BACKEND_PORT/api/cache/stats 2>/dev/null | grep -o '"using_redis":[^,]*' | cut -d: -f2)
            if [ "$cache_info" = "true" ]; then
                echo -e "  ${GREEN}✓ Conversation Cache: Redis${NC}"
            else
                echo -e "  ${YELLOW}✓ Conversation Cache: Fallback${NC}"
            fi
        fi
    else
        echo -e "${RED}STOPPED${NC}"
    fi
    
    echo -n "Frontend (port $FRONTEND_PORT): "
    if check_port $FRONTEND_PORT; then
        echo -e "${GREEN}RUNNING${NC}"
    else
        echo -e "${RED}STOPPED${NC}"
    fi
    
    # Check Redis status
    echo -n "Redis Cache: "
    if command -v redis-cli >/dev/null 2>&1 && redis-cli ping >/dev/null 2>&1; then
        echo -e "${GREEN}RUNNING${NC}"
    else
        echo -e "${YELLOW}NOT AVAILABLE${NC} (using fallback)"
    fi
    
    echo ""
    echo "URLs:"
    echo "  Frontend: http://localhost:$FRONTEND_PORT"
    echo "  Backend API: http://localhost:$BACKEND_PORT"
    echo "  ErrorLogger: http://localhost:$ERRORLOGGER_PORT"
    echo "  Cache Stats: http://localhost:$BACKEND_PORT/api/cache/stats"
}

# Function to stop all services
stop_services() {
    print_status "Stopping all services..."
    
    if [ -f "$PIDS_FILE" ]; then
        while IFS=':' read -r service pid; do
            if [ ! -z "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                print_status "Stopping $service (PID: $pid)"
                kill "$pid" 2>/dev/null || true
            fi
        done < "$PIDS_FILE"
        rm -f "$PIDS_FILE"
    fi
    
    # Force stop any remaining processes on our ports
    for port in $ERRORLOGGER_PORT $BACKEND_PORT $FRONTEND_PORT; do
        local pid=$(get_pid_by_port $port)
        if [ ! -z "$pid" ]; then
            print_status "Force stopping process on port $port (PID: $pid)"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
    
    print_success "All services stopped"
}

# Function to restart all services
restart_services() {
    stop_services
    sleep 2
    start_all_services
}

# Function to start all services
start_all_services() {
    print_status "🚀 Starting AI Service Platform"
    print_status "==============================="
    
    # Check prerequisites
    check_venv
    activate_venv
    
    # Initialize PID tracking
    rm -f "$PIDS_FILE"
    touch "$PIDS_FILE"
    
    # Start services in order
    start_errorlogger
    sleep 3  # Give ErrorLogger time to fully initialize
    
    start_backend
    sleep 5  # Give Backend time to initialize
    
    start_frontend
    
    echo ""
    print_success "🎉 AI Service Platform started successfully!"
    echo ""
    show_status
    
    echo ""
    print_status "💡 Tips:"
    echo "  - Use 'Ctrl+C' to stop this script"
    echo "  - Run '$0 stop' to stop all services"
    echo "  - Run '$0 status' to check service status"
    echo "  - Log files are in each service directory"
    echo ""
    print_status "🧠 Conversation Cache Features:"
    echo "  - Each AI agent remembers last 10 conversations"
    echo "  - Context automatically included in AI responses"
    echo "  - Cache stats: http://localhost:$BACKEND_PORT/api/cache/stats"
    echo "  - Agent conversations: http://localhost:$BACKEND_PORT/api/agents/{agent-id}/conversations"
    
    # Keep script running and monitor services
    trap 'stop_services; exit 0' INT TERM
    
    print_status "Monitoring services... (Press Ctrl+C to stop)"
    while true; do
        sleep 30
        # Optional: Add health checks here
    done
}

# Main script logic
case "${1:-start}" in
    "start")
        start_all_services
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        restart_services
        ;;
    "status")
        show_status
        ;;
    "help"|"-h"|"--help")
        echo "AI Service Startup Script"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start     Start all services (default)"
        echo "  stop      Stop all services"
        echo "  restart   Restart all services"
        echo "  status    Show service status"
        echo "  help      Show this help message"
        echo ""
        echo "This script will:"
        echo "  1. Check and activate the virtual environment"
        echo "  2. Start ErrorLogger service (port 5001)"
        echo "  3. Start AI Backend service (port 5000)"
        echo "  4. Start React Frontend (port 3000)"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
