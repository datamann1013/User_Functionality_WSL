#!/bin/bash
# AI Service Startup Script
# Starts 4 separate servers: ErrorLogger + Ollama Service + Backend + Frontend

set -e

# Handle sudo installation mode
if [[ "$EUID" -eq 0 ]]; then
    # Running as root - handle Ollama installation
    if ! command -v ollama >/dev/null 2>&1; then
        echo "🔧 Installing Ollama (running as root)..."
        curl -fsSL https://ollama.ai/install.sh | sh
        echo "✅ Ollama installation complete!"
        echo ""
        echo "🚀 Please run this script again as a regular user:"
        echo "   ./start_ai_service.sh"
        exit 0
    else
        echo "✅ Ollama already installed. Please run as regular user:"
        echo "   ./start_ai_service.sh"
        exit 0
    fi
fi

# Configuration
AI_SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$AI_SERVICE_DIR/../.." && pwd)"
BACKEND_DIR="$AI_SERVICE_DIR/backend"
OLLAMA_SERVICE_DIR="$AI_SERVICE_DIR/ollama_service"
FRONTEND_DIR="$AI_SERVICE_DIR/frontend"
VENV_DIR="$PROJECT_ROOT/venv"

# Service ports (configurable for different machines)
ERRORLOGGER_PORT=${ERRORLOGGER_PORT:-5001}
OLLAMA_SERVICE_PORT=${OLLAMA_SERVICE_PORT:-5002}
BACKEND_PORT=${BACKEND_PORT:-5000}
FRONTEND_PORT=${FRONTEND_PORT:-3000}

# Service URLs
ERRORLOGGER_URL="http://127.0.0.1:$ERRORLOGGER_PORT"
OLLAMA_SERVICE_URL="http://127.0.0.1:$OLLAMA_SERVICE_PORT"
BACKEND_URL="http://127.0.0.1:$BACKEND_PORT"
FRONTEND_URL="http://127.0.0.1:$FRONTEND_PORT"

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
    curl -s "$url/health" >/dev/null 2>&1
}

# Wait for service to be ready
wait_for_service() {
    local url="$1"
    local name="$2"
    local timeout="${3:-30}"
    
    log_info "Waiting for $name to be ready..."
    
    for i in $(seq 1 $timeout); do
        if check_service "$url"; then
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

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Setup environment and dependencies
setup_environment() {
    log_info "🔧 Setting up environment and dependencies..."
    
    # Check Python installation
    if ! command -v python3 >/dev/null 2>&1; then
        log_error "Python3 not found. Installing Python3..."
        if command -v apt >/dev/null 2>&1; then
            sudo apt update && sudo apt install -y python3 python3-pip python3-venv
        elif command -v yum >/dev/null 2>&1; then
            sudo yum install -y python3 python3-pip
        elif command -v pacman >/dev/null 2>&1; then
            sudo pacman -S python python-pip
        else
            log_error "Could not install Python3. Please install manually."
            return 1
        fi
    fi
    
    # Check Node.js installation
    if ! command -v node >/dev/null 2>&1; then
        log_info "Node.js not found. Installing Node.js..."
        if command -v apt >/dev/null 2>&1; then
            # Ubuntu/Debian
            log_info "Installing Node.js via package manager..."
            sudo apt update
            sudo apt install -y nodejs npm
        elif command -v yum >/dev/null 2>&1; then
            # CentOS/RHEL/Fedora
            log_info "Installing Node.js via package manager..."
            sudo yum install -y nodejs npm
        elif command -v dnf >/dev/null 2>&1; then
            # Fedora
            log_info "Installing Node.js via package manager..."
            sudo dnf install -y nodejs npm
        elif command -v pacman >/dev/null 2>&1; then
            # Arch Linux
            log_info "Installing Node.js via package manager..."
            sudo pacman -S nodejs npm
        elif command -v curl >/dev/null 2>&1; then
            # Try NodeSource installation
            log_info "Installing Node.js via NodeSource..."
            curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
            sudo apt-get install -y nodejs
        else
            log_error "Could not install Node.js automatically. Please install manually:"
            log_info "  Visit: https://nodejs.org/"
            log_info "  Or use your package manager:"
            log_info "    Ubuntu/Debian: sudo apt install nodejs npm"
            log_info "    CentOS/RHEL: sudo yum install nodejs npm"
            log_info "    Fedora: sudo dnf install nodejs npm"
            log_info "    Arch: sudo pacman -S nodejs npm"
            return 1
        fi
        
        # Verify installation
        if ! command -v node >/dev/null 2>&1; then
            log_error "Node.js installation failed"
            return 1
        fi
        log_success "✅ Node.js installed successfully ($(node --version))"
    else
        log_success "✅ Node.js already installed ($(node --version))"
    fi
    
    # Check npm
    if ! command -v npm >/dev/null 2>&1; then
        log_info "npm not found. Installing npm..."
        if command -v apt >/dev/null 2>&1; then
            sudo apt install -y npm
        elif command -v yum >/dev/null 2>&1; then
            sudo yum install -y npm
        elif command -v pacman >/dev/null 2>&1; then
            sudo pacman -S npm
        fi
    fi
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "$VENV_DIR" ]]; then
        log_info "Creating Python virtual environment at: $VENV_DIR"
        python3 -m venv "$VENV_DIR"
        if [[ $? -ne 0 ]]; then
            log_error "Failed to create virtual environment"
            return 1
        fi
        log_success "✅ Virtual environment created"
    else
        log_success "✅ Virtual environment already exists"
    fi
    
    # Activate virtual environment and upgrade pip
    log_info "Activating virtual environment and updating pip..."
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip setuptools wheel
    
    # Install Python dependencies for ErrorLogger
    log_info "Installing ErrorLogger dependencies..."
    cd "$PROJECT_ROOT/projects/ErrorLogger"
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        log_success "✅ ErrorLogger dependencies installed"
    fi
    
    # Install Python dependencies for Backend
    log_info "Installing Backend dependencies..."
    cd "$BACKEND_DIR"
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        log_success "✅ Backend dependencies installed"
    fi
    
    # Install Python dependencies for Ollama Service
    log_info "Installing Ollama Service dependencies..."
    cd "$OLLAMA_SERVICE_DIR"
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
    else
        # Install basic dependencies for ollama service
        pip install requests flask flask-cors
    fi
    log_success "✅ Ollama Service dependencies installed"
    
    # Install Frontend dependencies
    log_info "Installing Frontend dependencies..."
    cd "$FRONTEND_DIR"
    if [[ -f "package.json" ]]; then
        npm install
        log_success "✅ Frontend dependencies installed"
    else
        log_warning "⚠️  No package.json found in frontend directory"
    fi
    
    # Check and install curl if needed
    if ! command -v curl >/dev/null 2>&1; then
        log_info "Installing curl..."
        if command -v apt >/dev/null 2>&1; then
            sudo apt install -y curl
        elif command -v yum >/dev/null 2>&1; then
            sudo yum install -y curl
        fi
    fi
    
    log_success "🎉 Environment setup complete!"
    return 0
}

# Start ErrorLogger Server
start_errorlogger() {
    log_info "🔧 Starting ErrorLogger Server (Port: $ERRORLOGGER_PORT)"
    cd "$PROJECT_ROOT/projects/ErrorLogger"
    
    if check_service "$ERRORLOGGER_URL"; then
        log_success "✅ ErrorLogger already running"
        return 0
    fi
    
    source "$VENV_DIR/bin/activate"
    python error_logger_service.py --port $ERRORLOGGER_PORT --host 127.0.0.1 > errorlogger.log 2>&1 &
    ERRORLOGGER_PID=$!
    echo $ERRORLOGGER_PID > errorlogger.pid
    
    if wait_for_service "$ERRORLOGGER_URL" "ErrorLogger" 10; then
        log_success "✅ ErrorLogger Server running (PID: $ERRORLOGGER_PID)"
        return 0
    else
        log_error "❌ ErrorLogger Server failed to start"
        return 1
    fi
}

# Check and install Ollama if needed
check_and_install_ollama() {
    log_info "🔍 Checking Ollama installation..."
    
    # Check if Ollama is installed
    if command -v ollama >/dev/null 2>&1; then
        log_success "✅ Ollama is already installed ($(ollama --version))"
        
        # Check if Ollama service is running
        if curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            log_success "✅ Ollama service is running"
        else
            log_info "🚀 Starting Ollama service..."
            sudo systemctl start ollama 2>/dev/null || {
                log_warning "⚠️  Could not start Ollama service automatically"
                log_info "You may need to run: sudo systemctl start ollama"
            }
        fi
        
        # Check for default model
        local models=$(curl -s http://127.0.0.1:11434/api/tags 2>/dev/null | grep -o '"name":"[^"]*"' | wc -l)
        if [ "$models" -eq 0 ]; then
            log_info "📥 No models found. The Ollama service will download llama3.2:1b automatically."
            log_info "This may take a few minutes on first run..."
        fi
        
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

# Start Ollama Service
start_ollama_service() {
    log_info "🧠 Starting Ollama Service (Port: $OLLAMA_SERVICE_PORT)"
    cd "$OLLAMA_SERVICE_DIR"
    
    if check_service "$OLLAMA_SERVICE_URL"; then
        log_success "✅ Ollama Service already running"
        return 0
    fi
    
    source "$VENV_DIR/bin/activate"
    
    # Set environment for Ollama service
    export ERRORLOGGER_SERVICE_URL="$ERRORLOGGER_URL/log"
    
    python ollama_api.py --port $OLLAMA_SERVICE_PORT --host 127.0.0.1 > ollama_service.log 2>&1 &
    OLLAMA_SERVICE_PID=$!
    
    if wait_for_service "$OLLAMA_SERVICE_URL" "Ollama Service" 30; then
        log_success "✅ Ollama Service running (PID: $OLLAMA_SERVICE_PID)"
        return 0
    else
        log_warning "⚠️  Ollama Service failed to start (AI will use demo mode)"
        return 1
    fi
}

# Start Backend Server
start_backend() {
    log_info "🤖 Starting Backend Server (Port: $BACKEND_PORT)"
    cd "$BACKEND_DIR"
    
    if check_service "$BACKEND_URL"; then
        log_success "✅ Backend already running"
        return 0
    fi
    
    source "$VENV_DIR/bin/activate"
    
    # Set environment for backend
    export ERRORLOGGER_SERVICE_URL="$ERRORLOGGER_URL/log"
    export OLLAMA_SERVICE_URL="$OLLAMA_SERVICE_URL"
    
    python app.py --port $BACKEND_PORT --host 127.0.0.1 > backend.log 2>&1 &
    BACKEND_PID=$!
    
    if wait_for_service "$BACKEND_URL" "Backend" 15; then
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
    cd "$FRONTEND_DIR"
    
    # Set environment for frontend
    export REACT_APP_BACKEND_URL="http://localhost:$BACKEND_PORT"
    export PORT=$FRONTEND_PORT
    
    npm start > frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    # Wait for frontend to start
    log_info "Waiting for React development server to start..."
    sleep 8
    
    if curl -s "$FRONTEND_URL" >/dev/null 2>&1; then
        log_success "✅ Frontend Server running (PID: $FRONTEND_PID)"
        return 0
    else
        log_warning "⚠️  Frontend may still be starting..."
        return 0
    fi
}

# Main startup function
main() {
    echo "🚀 AI Service - Four Server Architecture"
    echo "   This will start 4 separate servers:"
    echo "   📊 ErrorLogger Server  (Port: $ERRORLOGGER_PORT)"
    echo "   🧠 Ollama Service       (Port: $OLLAMA_SERVICE_PORT)"
    echo "   🤖 Backend Server      (Port: $BACKEND_PORT)" 
    echo "   🌐 Frontend Server     (Port: $FRONTEND_PORT)"
    echo

    # Check and setup prerequisites
    log_info "🔍 Checking system requirements..."
    setup_environment || exit 1

    # Start services in sequence
    if ! start_errorlogger; then
        log_error "Failed to start ErrorLogger service"
        exit 1
    fi
    
    # Check and install Ollama before starting the service
    check_and_install_ollama
    
    # Start Ollama service (non-critical - continue if it fails)
    start_ollama_service || log_warning "⚠️  Continuing without Ollama service"
    
    if ! start_backend; then
        log_error "Failed to start Backend service"
        exit 1
    fi
    
    if ! start_frontend; then
        log_error "Failed to start Frontend service"
        exit 1
    fi

    echo
    log_success "🎉 All servers are running!"
    echo
    log_info "Access your services:"
    log_info "  🌐 Frontend:     $FRONTEND_URL"
    log_info "  🤖 Backend API:  $BACKEND_URL"
    log_info "  🧠 Ollama API:   $OLLAMA_SERVICE_URL"
    log_info "  📊 ErrorLogger:  $ERRORLOGGER_URL"
    log_info "  📊 ErrorLogger:  $ERRORLOGGER_URL"
    echo
    log_info "Logs:"
    log_info "  ErrorLogger: $PROJECT_ROOT/projects/ErrorLogger/errorlogger.log"
    log_info "  Backend:     $BACKEND_DIR/backend.log"
    log_info "  Frontend:    $FRONTEND_DIR/frontend.log"
    echo
    log_info "Press Ctrl+C to stop all services..."
    
    # Keep script running and monitor services
    while true; do
        sleep 10
        
        # Check if all services are still running
        all_running=true
        
        if ! check_service "$ERRORLOGGER_URL"; then
            log_warning "⚠️  ErrorLogger service appears to be down"
            all_running=false
        fi
        
        if ! check_service "$BACKEND_URL"; then
            log_warning "⚠️  Backend service appears to be down" 
            all_running=false
        fi
        
        if ! curl -s "$FRONTEND_URL" >/dev/null 2>&1; then
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
