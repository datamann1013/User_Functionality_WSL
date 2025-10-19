#!/bin/bash
# ============================================================================
# RuneCore AI Subsystem Installation & Startup Script
# ============================================================================
# This script handles EVERYTHING needed to run the RuneCore AI subsystem:
# - System dependencies installation
# - Python/Node.js installation 
# - Virtual environment setup
# - All Python/Node package installation
# - Ollama installation (with sudo prompt)
# - RuneCore AI services startup and monitoring
# - Comprehensive error handling and logging
# ============================================================================

set -e  # Exit on any error

# Handle sudo installation mode for Ollama only
if [[ "$EUID" -eq 0 && "$1" == "--install-ollama-only" ]]; then
    echo "🔧 Installing Ollama (running as root)..."
    curl -fsSL https://ollama.ai/install.sh | sh
    echo "Ollama installation complete!"
    echo ""
    echo "Please run this script again as a regular user:"
    echo "   ./start_ai_service.sh"
    exit 0
fi

# Warn if running as root (except for ollama-only mode)
if [[ "$EUID" -eq 0 ]]; then
    echo "⚠️  Warning: Running as root is not recommended for the main installation"
    echo "This script will handle sudo prompts when needed."
    echo ""
    echo "If you only want to install Ollama as root, run:"
    echo "   sudo ./start_ai_service.sh --install-ollama-only"
    echo ""
    echo "Otherwise, run as regular user:"
    echo "   ./start_ai_service.sh"
    exit 1
fi

# ============================================================================
# CONFIGURATION & GLOBALS
# ============================================================================

# Get script directory and project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AI_SERVICE_DIR="$SCRIPT_DIR"
BACKEND_DIR="$AI_SERVICE_DIR/backend"
OLLAMA_SERVICE_DIR="$AI_SERVICE_DIR/ollama_service"
FRONTEND_DIR="$AI_SERVICE_DIR/frontend"
ERRORLOGGER_DIR="$PROJECT_ROOT/projects/ErrorLogger"
VENV_DIR="$PROJECT_ROOT/venv"

# Service ports (configurable)
export ERRORLOGGER_PORT=${ERRORLOGGER_PORT:-5001}
export OLLAMA_SERVICE_PORT=${OLLAMA_SERVICE_PORT:-5002}
export BACKEND_PORT=${BACKEND_PORT:-5000}
export FRONTEND_PORT=${FRONTEND_PORT:-3000}

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
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Process IDs for cleanup
ERRORLOGGER_PID=""
OLLAMA_SERVICE_PID=""
BACKEND_PID=""
FRONTEND_PID=""

# ============================================================================
# LOGGING AND UTILITY FUNCTIONS
# ============================================================================

log_header() { echo -e "${PURPLE}=== $1 ===${NC}"; }
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_install() { echo -e "${CYAN}[INSTALL]${NC} $1"; }

# Check if running as root
is_root() {
    [[ "$EUID" -eq 0 ]]
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if service is responding
check_service() {
    local url="$1"
    curl -s "$url/health" >/dev/null 2>&1
}

# Wait for service with timeout
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
        echo -n "."
        sleep 1
    done
    echo ""
    
    log_error "$name failed to start within $timeout seconds"
    return 1
}

# Detect Linux distribution
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        echo "$ID"
    elif command_exists lsb_release; then
        lsb_release -si | tr '[:upper:]' '[:lower:]'
    elif [[ -f /etc/redhat-release ]]; then
        echo "redhat"
    elif [[ -f /etc/debian_version ]]; then
        echo "debian"
    else
        echo "unknown"
    fi
}

# Check if we need sudo for package installation
needs_sudo() {
    # If we're root, we don't need sudo
    if is_root; then
        return 1
    fi
    
    # Test if we can actually use package managers with sudo
    if command_exists pacman; then
        # Test if sudo works and we can use pacman
        if sudo -n pacman -Q >/dev/null 2>&1; then
            return 0  # We need sudo but it's available
        elif pacman -Q >/dev/null 2>&1; then
            return 1  # Can run without sudo
        else
            return 0  # Need sudo
        fi
    elif command_exists apt; then
        # Test if we can list packages
        if apt list --installed >/dev/null 2>&1; then
            return 1  # Don't need sudo for this test, but will need for install
        else
            return 0  # Need sudo
        fi
    elif command_exists yum; then
        if yum list installed >/dev/null 2>&1; then
            return 1
        else
            return 0
        fi
    elif command_exists dnf; then
        if dnf list installed >/dev/null 2>&1; then
            return 1
        else
            return 0
        fi
    else
        return 0  # Assume we need sudo if we can't detect
    fi
}

# ============================================================================
# SYSTEM DEPENDENCIES INSTALLATION  
# ============================================================================

install_system_packages() {
    log_header "Installing System Dependencies"
    
    local distro=$(detect_distro)
    local sudo_cmd=""
    
    # Determine if we need sudo and if it's available
    if ! is_root; then
        if command_exists sudo; then
            # Test if sudo works
            if sudo -n true >/dev/null 2>&1; then
                sudo_cmd="sudo"
                log_info "Using sudo for package installation (passwordless)"
            elif sudo -l >/dev/null 2>&1; then
                sudo_cmd="sudo"
                log_warning "Will prompt for sudo password for package installation"
            else
                log_error "sudo is not available or configured for this user"
                log_info "Please ensure you have sudo access or run as root"
                exit 1
            fi
        else
            log_error "This script requires sudo access for package installation"
            log_info "Please install sudo or run as root"
            exit 1
        fi
    fi
    
    # Check if essential tools are already installed
    local missing_tools=()
    local essential_tools=("curl" "git")
    
    for tool in "${essential_tools[@]}"; do
        if ! command_exists "$tool"; then
            missing_tools+=("$tool")
        fi
    done
    
    # Check language runtimes
    if ! command_exists python3; then
        missing_tools+=("python3")
    fi
    
    if ! command_exists node; then
        missing_tools+=("nodejs")
    fi
    
    # If nothing is missing, skip installation
    if [[ ${#missing_tools[@]} -eq 0 ]]; then
        log_success "All essential system dependencies already installed"
        return 0
    fi
    
    log_info "Missing tools: ${missing_tools[*]}"
    
    # Update package lists first
    log_install "Updating package lists..."
    case "$distro" in
        ubuntu|debian)
            $sudo_cmd apt update -y || {
                log_error "Failed to update package lists"
                exit 1
            }
            ;;
        fedora)
            $sudo_cmd dnf check-update || true
            ;;
        centos|rhel|rocky|almalinux)
            $sudo_cmd yum check-update || true
            ;;
        arch|manjaro)
            $sudo_cmd pacman -Sy || {
                log_error "Failed to update package lists"
                exit 1
            }
            ;;
    esac
    
    # Install packages based on distribution
    case "$distro" in
        ubuntu|debian)
            log_install "Installing packages for Ubuntu/Debian..."
            $sudo_cmd apt install -y curl wget git build-essential pkg-config python3 python3-pip python3-venv nodejs npm || {
                log_error "Package installation failed"
                exit 1
            }
            ;;
        fedora)
            log_install "Installing packages for Fedora..."
            $sudo_cmd dnf install -y curl wget git gcc gcc-c++ make python3 python3-pip nodejs npm || {
                log_error "Package installation failed"
                exit 1
            }
            ;;
        centos|rhel|rocky|almalinux)
            log_install "Installing packages for CentOS/RHEL..."
            # Enable EPEL repository first
            $sudo_cmd yum install -y epel-release || true
            $sudo_cmd yum install -y curl wget git gcc gcc-c++ make python3 python3-pip || {
                log_error "Package installation failed"
                exit 1
            }
            
            # Install Node.js from NodeSource
            if ! command_exists node; then
                log_install "Installing Node.js from NodeSource..."
                curl -fsSL https://rpm.nodesource.com/setup_lts.x | $sudo_cmd bash -
                $sudo_cmd yum install -y nodejs
            fi
            ;;
        arch|manjaro)
            log_install "Installing packages for Arch Linux..."
            $sudo_cmd pacman -S --noconfirm curl wget git base-devel python python-pip nodejs npm || {
                log_error "Package installation failed"
                exit 1
            }
            ;;
        *)
            log_warning "Unknown distribution: $distro"
            log_info "Please ensure these packages are installed manually:"
            log_info "  - curl, wget, git"
            log_info "  - python3, python3-pip, python3-venv"
            log_info "  - nodejs, npm"
            log_info "  - build tools (gcc, make, etc.)"
            ;;
    esac
    
    # Verify critical installations
    local verification_failed=0
    
    if ! command_exists python3; then
        log_error "Python3 installation failed"
        verification_failed=1
    else
        local python_version=$(python3 --version 2>&1)
        log_success "Python3 installed: $python_version"
    fi
    
    if ! command_exists node; then
        log_error "Node.js installation failed"
        verification_failed=1
    else
        local node_version=$(node --version 2>&1)
        log_success "Node.js installed: $node_version"
    fi
    
    if ! command_exists npm; then
        log_error "npm installation failed"
        verification_failed=1
    else
        local npm_version=$(npm --version 2>&1)
        log_success "npm installed: $npm_version"
    fi
    
    if [[ $verification_failed -eq 1 ]]; then
        log_error "Some critical packages failed to install"
        exit 1
    fi
    
    log_success "System dependencies installation completed"
}

setup_python_environment() {
    log_header "Setting up Python Environment"
    
    # Verify Python installation
    if ! command_exists python3; then
        log_error "Python3 not found after installation!"
        log_info "Please install Python3 manually and run this script again"
        exit 1
    fi
    
    local python_version=$(python3 --version 2>&1)
    log_success "Found Python: $python_version"
    
    # Create virtual environment
    if [[ ! -d "$VENV_DIR" ]]; then
        log_install "Creating virtual environment at: $VENV_DIR"
        python3 -m venv "$VENV_DIR"
        if [[ $? -ne 0 ]]; then
            log_error "Failed to create virtual environment"
            log_info "Trying alternative method..."
            # Try with --system-site-packages as fallback
            python3 -m venv --system-site-packages "$VENV_DIR" || {
                log_error "Virtual environment creation failed completely"
                exit 1
            }
        fi
        log_success "Virtual environment created successfully"
    else
        log_success "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    log_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip and essential tools
    log_install "Upgrading pip and essential Python tools..."
    pip install --upgrade pip setuptools wheel || {
        log_warning "Failed to upgrade pip/setuptools, continuing..."
    }
    
    log_success "Python environment ready"
}

install_python_dependencies() {
    log_header "Installing Python Dependencies"
    
    # Ensure virtual environment is activated
    source "$VENV_DIR/bin/activate"
    
    # 1. ErrorLogger dependencies
    if [[ -f "$ERRORLOGGER_DIR/requirements.txt" ]]; then
        log_install "Installing ErrorLogger dependencies..."
        cd "$ERRORLOGGER_DIR"
        pip install -r requirements.txt || {
            log_warning "Some ErrorLogger dependencies failed, installing manually..."
            pip install flask flask-cors requests python-dotenv || {
                log_error "Failed to install ErrorLogger dependencies"
                exit 1
            }
        }
        log_success "ErrorLogger dependencies installed"
    else
        log_install "Installing ErrorLogger dependencies manually..."
        pip install flask flask-cors requests python-dotenv
        log_success "ErrorLogger dependencies installed"
    fi
    
    # 2. Backend dependencies
    if [[ -f "$BACKEND_DIR/requirements.txt" ]]; then
        log_install "Installing Backend dependencies..."
        cd "$BACKEND_DIR"
        pip install -r requirements.txt || {
            log_warning "Some Backend dependencies failed, installing manually..."
            pip install flask flask-cors requests python-dotenv || {
                log_error "Failed to install Backend dependencies"
                exit 1
            }
        }
        log_success "Backend dependencies installed"
    else
        log_install "Installing Backend dependencies manually..."
        pip install flask flask-cors requests python-dotenv
        log_success "Backend dependencies installed"
    fi
    
    # 3. Ollama Service dependencies
    log_install "Installing Ollama Service dependencies..."
    pip install flask flask-cors requests python-dotenv
    log_success "Ollama Service dependencies installed"
    
    log_success "All Python dependencies installed"
}

setup_nodejs_environment() {
    log_header "Setting up Node.js Environment"
    
    # Verify Node.js installation
    if ! command_exists node; then
        log_error "Node.js not found after installation!"
        log_info "Please install Node.js manually and run this script again"
        exit 1
    fi
    
    if ! command_exists npm; then
        log_error "npm not found after installation!"
        log_info "Please install npm manually and run this script again"
        exit 1
    fi
    
    local node_version=$(node --version 2>&1)
    local npm_version=$(npm --version 2>&1)
    log_success "Found Node.js: $node_version"
    log_success "Found npm: $npm_version"
    
    # Install frontend dependencies
    if [[ -f "$FRONTEND_DIR/package.json" ]]; then
        log_install "Installing Frontend dependencies..."
        cd "$FRONTEND_DIR"
        
        # Clear npm cache if there are issues
        npm cache clean --force 2>/dev/null || true
        
        # Install dependencies
        npm install || {
            log_warning "npm install failed, trying alternative methods..."
            
            # Try with legacy peer deps
            npm install --legacy-peer-deps || {
                # Try with force
                npm install --force || {
                    log_error "Failed to install frontend dependencies"
                    log_info "You may need to manually run 'npm install' in $FRONTEND_DIR"
                    exit 1
                }
            }
        }
        log_success "Frontend dependencies installed"
    else
        log_warning "No package.json found in frontend directory"
        log_info "Frontend may not be properly configured"
    fi
    
    log_success "Node.js environment ready"
}

install_ollama() {
    log_header "Ollama Installation Check"
    
    # Check if Ollama is already installed
    if command_exists ollama; then
        local ollama_version=$(ollama --version 2>&1 || echo "unknown")
        log_success "Ollama already installed: $ollama_version"
        
        # Start ollama service if not running
        if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
            log_info "Starting Ollama service..."
            if command_exists systemctl; then
                sudo systemctl start ollama 2>/dev/null || {
                    log_info "Attempting to start Ollama manually..."
                    ollama serve >/dev/null 2>&1 &
                    sleep 3
                }
            else
                ollama serve >/dev/null 2>&1 &
                sleep 3
            fi
        fi
        
        return 0
    fi
    
    log_warning "Ollama not found!"
    log_info "Ollama is required for AI functionality (without it, only demo mode available)"
    echo
    
    echo -e "${YELLOW}╭─────────────────────────────────────────────────────────────╮${NC}"
    echo -e "${YELLOW}│  OLLAMA INSTALLATION REQUIRED                              │${NC}"
    echo -e "${YELLOW}├─────────────────────────────────────────────────────────────┤${NC}"
    echo -e "${YELLOW}│  Ollama needs to be installed with root privileges.        │${NC}"
    echo -e "${YELLOW}│                                                             │${NC}"
    echo -e "${YELLOW}│  Options:                                                   │${NC}"
    echo -e "${YELLOW}│  1. Install now with sudo (recommended)                    │${NC}"
    echo -e "${YELLOW}│  2. Skip and run in demo mode only                         │${NC}"
    echo -e "${YELLOW}│  3. Exit and install manually                              │${NC}"
    echo -e "${YELLOW}╰─────────────────────────────────────────────────────────────╯${NC}"
    echo
    
    while true; do
        read -p "Choose option [1-3]: " choice
        case $choice in
            1)
                log_install "Installing Ollama with sudo..."
                if command_exists sudo; then
                    curl -fsSL https://ollama.ai/install.sh | sudo sh || {
                        log_error "Ollama installation failed"
                        log_info "Continuing without Ollama (demo mode only)"
                        return 1
                    }
                    log_success "Ollama installation completed"
                    
                    # Start ollama service
                    if command_exists systemctl; then
                        log_info "Starting Ollama service..."
                        sudo systemctl enable ollama 2>/dev/null || true
                        sudo systemctl start ollama 2>/dev/null || true
                    fi
                    
                    return 0
                else
                    log_error "sudo not available for Ollama installation"
                    return 1
                fi
                ;;
            2)
                log_warning "Skipping Ollama installation (demo mode only)"
                return 1
                ;;
            3)
                log_info "Manual installation:"
                log_info "  curl -fsSL https://ollama.ai/install.sh | sh"
                exit 0
                ;;
            *)
                echo "Please choose 1, 2, or 3"
                ;;
        esac
    done
}

# ============================================================================
# SERVICE STARTUP FUNCTIONS
# ============================================================================

start_errorlogger() {
    log_header "Starting ErrorLogger Service"
    
    # Check if already running
    if check_service "$ERRORLOGGER_URL"; then
        log_success "ErrorLogger already running"
        return 0
    fi
    
    cd "$ERRORLOGGER_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Check which error server file exists
    local server_script=""
    if [[ -f "error_server.py" ]]; then
        server_script="error_server.py"
    elif [[ -f "error_logger_service.py" ]]; then
        server_script="error_logger_service.py"
    else
        log_error "No ErrorLogger server script found!"
        log_info "Looking for: error_server.py or error_logger_service.py"
        return 1
    fi
    
    log_install "Starting ErrorLogger with $server_script..."
    
    # Set environment
    export ERRORLOGGER_HOST="127.0.0.1"
    export ERRORLOGGER_PORT="$ERRORLOGGER_PORT"
    
    # Start service
    python "$server_script" > errorlogger.log 2>&1 &
    ERRORLOGGER_PID=$!
    echo $ERRORLOGGER_PID > errorlogger.pid
    
    # Wait for service
    if wait_for_service "$ERRORLOGGER_URL" "ErrorLogger" 15; then
        log_success "ErrorLogger running (PID: $ERRORLOGGER_PID, Port: $ERRORLOGGER_PORT)"
        return 0
    else
        log_error "ErrorLogger failed to start"
        log_info "Check logs: $ERRORLOGGER_DIR/errorlogger.log"
        return 1
    fi
}

start_ollama_service() {
    log_header "Starting Ollama Service"
    
    # Check if already running
    if check_service "$OLLAMA_SERVICE_URL"; then
        log_success "Ollama Service already running"
        return 0
    fi
    
    cd "$OLLAMA_SERVICE_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Check if ollama_api.py exists
    if [[ ! -f "ollama_api.py" ]]; then
        log_error "ollama_api.py not found in $OLLAMA_SERVICE_DIR"
        return 1
    fi
    
    log_install "Starting Ollama Service..."
    
    # Set environment
    export OLLAMA_HOST="http://localhost:11434"
    export ERRORLOGGER_SERVICE_URL="$ERRORLOGGER_URL/log"
    export PORT="$OLLAMA_SERVICE_PORT"
    
    # Start service
    python ollama_api.py > ollama_service.log 2>&1 &
    OLLAMA_SERVICE_PID=$!
    
    # Wait for service
    if wait_for_service "$OLLAMA_SERVICE_URL" "Ollama Service" 30; then
        log_success "Ollama Service running (PID: $OLLAMA_SERVICE_PID, Port: $OLLAMA_SERVICE_PORT)"
        return 0
    else
        log_warning "Ollama Service failed to start (AI will use demo mode)"
        log_info "Check logs: $OLLAMA_SERVICE_DIR/ollama_service.log"
        return 1
    fi
}

start_backend() {
    log_header "Starting Backend Service"
    
    # Check if already running
    if check_service "$BACKEND_URL"; then
        log_success "Backend already running"
        return 0
    fi
    
    cd "$BACKEND_DIR"
    source "$VENV_DIR/bin/activate"
    
    # Check if app.py exists
    if [[ ! -f "app.py" ]]; then
        log_error "app.py not found in $BACKEND_DIR"
        return 1
    fi
    
    log_install "Starting Backend Service..."
    
    # Set environment
    export ERRORLOGGER_SERVICE_URL="$ERRORLOGGER_URL/log"
    export OLLAMA_SERVICE_URL="$OLLAMA_SERVICE_URL"
    export PORT="$BACKEND_PORT"
    
    # Start service
    python app.py > backend.log 2>&1 &
    BACKEND_PID=$!
    
    # Wait for service
    if wait_for_service "$BACKEND_URL" "Backend" 15; then
        log_success "Backend running (PID: $BACKEND_PID, Port: $BACKEND_PORT)"
        return 0
    else
        log_error "Backend failed to start"
        log_info "Check logs: $BACKEND_DIR/backend.log"
        return 1
    fi
}

start_frontend() {
    log_header "Starting Frontend Service"
    
    cd "$FRONTEND_DIR"
    
    # Check if package.json exists
    if [[ ! -f "package.json" ]]; then
        log_error "package.json not found in $FRONTEND_DIR"
        return 1
    fi
    
    log_install "Starting Frontend Service..."
    
    # Set environment
    export REACT_APP_API_URL="http://localhost:$BACKEND_PORT"
    export PORT="$FRONTEND_PORT"
    export BROWSER="none"  # Don't auto-open browser
    
    # Start service
    npm start > frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    # Wait for React to start (takes longer)
    log_info "Waiting for React development server..."
    sleep 10
    
    # Check if frontend is responding
    if curl -s "$FRONTEND_URL" >/dev/null 2>&1; then
        log_success "Frontend running (PID: $FRONTEND_PID, Port: $FRONTEND_PORT)"
        return 0
    else
        log_warning "Frontend may still be starting (check $FRONTEND_URL in a minute)"
        return 0
    fi
}

# ============================================================================
# CLEANUP AND MONITORING
# ============================================================================

cleanup_services() {
    log_header "Shutting Down Services"
    
    # Stop all services
    if [[ -n "$FRONTEND_PID" ]]; then
        log_info "Stopping Frontend service..."
        kill "$FRONTEND_PID" 2>/dev/null || true
        wait "$FRONTEND_PID" 2>/dev/null || true
    fi
    
    if [[ -n "$BACKEND_PID" ]]; then
        log_info "Stopping Backend service..."
        kill "$BACKEND_PID" 2>/dev/null || true
        wait "$BACKEND_PID" 2>/dev/null || true
    fi
    
    if [[ -n "$OLLAMA_SERVICE_PID" ]]; then
        log_info "Stopping Ollama Service..."
        kill "$OLLAMA_SERVICE_PID" 2>/dev/null || true
        wait "$OLLAMA_SERVICE_PID" 2>/dev/null || true
    fi
    
    if [[ -n "$ERRORLOGGER_PID" ]]; then
        log_info "Stopping ErrorLogger service..."
        kill "$ERRORLOGGER_PID" 2>/dev/null || true
        wait "$ERRORLOGGER_PID" 2>/dev/null || true
        rm -f "$ERRORLOGGER_DIR/errorlogger.pid"
    fi
    
    log_success "All services stopped"
}

monitor_services() {
    log_header "Service Monitoring Started"
    
    log_info "Services are running! Press Ctrl+C to stop all services"
    echo
    log_info "Service URLs:"
    log_info "  Frontend:     $FRONTEND_URL"
    log_info "  Backend API:  $BACKEND_URL/health"
    log_info "  Ollama API:   $OLLAMA_SERVICE_URL/health" 
    log_info "  ErrorLogger:  $ERRORLOGGER_URL/health"
    echo
    log_info "Log files:"
    log_info "  ErrorLogger:  $ERRORLOGGER_DIR/errorlogger.log"
    log_info "  Backend:      $BACKEND_DIR/backend.log"
    log_info "  Ollama:       $OLLAMA_SERVICE_DIR/ollama_service.log"
    log_info "  Frontend:     $FRONTEND_DIR/frontend.log"
    echo
    
    # Monitor loop
    while true; do
        sleep 30
        
        # Check services health
        local issues=0
        
        if ! check_service "$ERRORLOGGER_URL"; then
            log_warning "⚠️  ErrorLogger service down"
            issues=$((issues + 1))
        fi
        
        if ! check_service "$BACKEND_URL"; then
            log_warning "⚠️  Backend service down"
            issues=$((issues + 1))
        fi
        
        if ! check_service "$OLLAMA_SERVICE_URL"; then
            log_warning "⚠️  Ollama service down (AI in demo mode)"
        fi
        
        if ! curl -s "$FRONTEND_URL" >/dev/null 2>&1; then
            log_warning "⚠️  Frontend service down"
            issues=$((issues + 1))
        fi
        
        if [[ $issues -gt 1 ]]; then
            log_error "Multiple critical services are down!"
            log_info "Check logs and consider restarting"
        fi
    done
}

# ============================================================================
# MAIN FUNCTION
# ============================================================================

main() {
    echo -e "${PURPLE}╭─────────────────────────────────────────────────────────────╮${NC}"
    echo -e "${PURPLE}│               RUNECORE AI SUBSYSTEM INSTALLER              │${NC}"
    echo -e "${PURPLE}│           AI System Setup & Service Management            │${NC}"
    echo -e "${PURPLE}╰─────────────────────────────────────────────────────────────╯${NC}"
    echo
    
    log_info "This script will:"
    log_info "  - Install all system dependencies"
    log_info "  - Set up Python virtual environment"
    log_info "  - Install all Python packages"
    log_info "  - Set up Node.js environment"
    log_info "  - Install all Node.js packages"
    log_info "  - Install Ollama (with permission)"
    log_info "  - Start all 4 services"
    log_info "  - Monitor service health"
    echo
    
    # Set up cleanup trap
    trap cleanup_services EXIT INT TERM
    
    # Installation phase
    log_header "INSTALLATION PHASE"
    
    install_system_packages
    setup_python_environment
    install_python_dependencies
    setup_nodejs_environment
    install_ollama  # Non-critical, can fail
    
    log_success "Installation phase completed!"
    echo
    
    # Startup phase
    log_header "SERVICE STARTUP PHASE"
    
    # Start services in dependency order
    if ! start_errorlogger; then
        log_error "Critical: ErrorLogger failed to start"
        exit 1
    fi
    
    start_ollama_service  # Non-critical
    
    if ! start_backend; then
        log_error "Critical: Backend failed to start"
        exit 1
    fi
    
    if ! start_frontend; then
        log_error "Critical: Frontend failed to start"
        exit 1
    fi
    
    log_success "All services started successfully!"
    echo
    
    # Monitoring phase
    monitor_services
}

# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

# Check for help flag
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "AI Service Complete Setup Script"
    echo
    echo "Usage: $0 [options]"
    echo
    echo "This script handles complete installation and startup of the AI service."
    echo "It will automatically install all dependencies and start all services."
    echo
    echo "Options:"
    echo "  --help, -h    Show this help message"
    echo "  --install-ollama-only  Install only Ollama (run as root)"
    echo
    echo "Environment variables:"
    echo "  ERRORLOGGER_PORT    Port for ErrorLogger service (default: 5001)"
    echo "  OLLAMA_SERVICE_PORT Port for Ollama service (default: 5002)"
    echo "  BACKEND_PORT        Port for Backend service (default: 5000)"
    echo "  FRONTEND_PORT       Port for Frontend service (default: 3000)"
    echo
    echo "The script will prompt for sudo access when needed for:"
    echo "  - System package installation"
    echo "  - Ollama installation"
    echo
    exit 0
fi

# Run main function
main "$@"
