#!/bin/bash

# RuneCore AI Ecosystem Remote Installer
# Usage: curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/install-runecore-remote.sh | bash
# Or: curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/install-runecore-remote.sh | bash -s -- --version=RuneCore_AI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
REPO_URL="https://github.com/datamann1013/RuneCore_Ecosystem"
RAW_URL="https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem"
DEFAULT_VERSION="main"
INSTALL_DIR="$HOME/RuneCore_Ecosystem"
VERSION=""
ACTION="install"
PURGE=false

# Directory this script lives in (used to find sibling uninstall script when run locally)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo "")"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --version=*)
            VERSION="${1#*=}"
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --install-dir=*)
            INSTALL_DIR="${1#*=}"
            shift
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --uninstall)
            ACTION="uninstall"
            shift
            ;;
        --reinstall)
            ACTION="reinstall"
            shift
            ;;
        --purge)
            PURGE=true
            shift
            ;;
        --help|-h)
            echo "RuneCore AI Ecosystem Remote Installer"
            echo ""
            echo "Usage: curl -sSL $RAW_URL/main/install-runecore-remote.sh | bash [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --version=VERSION     Version/branch to install (default: main)"
            echo "  --install-dir=DIR     Installation directory (default: $HOME/RuneCore_Ecosystem)"
            echo "  --uninstall          Remove RuneCore (delegates to uninstall-runecore.sh)"
            echo "  --reinstall          Uninstall then install fresh in one run"
            echo "  --purge              With --uninstall/--reinstall: also wipe data volumes + .env"
            echo "                       (default preserves databases, models, certs, logs and .env)"
            echo "  --help               Show this help message"
            echo ""
            echo "Available versions:"
            echo "  main                 Latest stable release"
            echo "  RuneCore_AI          AI module development branch (RuneCore_Mind)"
            echo "  experimental        Experimental features"
            echo "  test                Testing branch"
            echo ""
            echo "Examples:"
            echo "  # Install latest stable"
            echo "  curl -sSL $RAW_URL/main/install-runecore-remote.sh | bash"
            echo ""
            echo "  # Install AI service branch"
            echo "  curl -sSL $RAW_URL/main/install-runecore-remote.sh | bash -s -- --version=RuneCore_AI"
            echo ""
            echo "  # Install to custom directory"
            echo "  curl -sSL $RAW_URL/main/install-runecore-remote.sh | bash -s -- --install-dir=/opt/runecore"
            echo ""
            echo "  # Re-run on an existing install (idempotent upgrade: stop, rebuild, restart;"
            echo "  # preserves data volumes and existing .env)"
            echo "  bash install-runecore-remote.sh"
            echo ""
            echo "  # Reinstall preserving data, or fully purge"
            echo "  bash install-runecore-remote.sh --reinstall"
            echo "  bash install-runecore-remote.sh --uninstall --purge"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Set version if not specified
if [[ -z "$VERSION" ]]; then
    VERSION="$DEFAULT_VERSION"
fi

print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                 RuneCore AI Ecosystem Installer              ║"
    echo "║                                                              ║"
    echo "║  🚀 Advanced AI Service Platform with Security-First Design  ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

check_requirements() {
    print_info "Checking system requirements..."
    
    # Check for required commands
    local required_commands=("git" "docker" "docker-compose" "curl" "python3")
    local missing_commands=()
    
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_commands+=("$cmd")
        fi
    done
    
    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        print_error "Missing required commands: ${missing_commands[*]}"
        print_info "Please install the missing dependencies and try again."
        print_info "On Ubuntu/Debian: sudo apt update && sudo apt install git docker.io docker-compose curl python3 python3-pip"
        print_info "On CentOS/RHEL: sudo yum install git docker docker-compose curl python3 python3-pip"
        print_info "On Arch: sudo pacman -S git docker docker-compose curl python"
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running or accessible"
        print_info "Please start Docker: sudo systemctl start docker"
        print_info "And add your user to docker group: sudo usermod -aG docker $USER"
        exit 1
    fi
    
    print_status "All requirements satisfied"
}

download_runecore() {
    print_info "Downloading RuneCore Ecosystem (version: $VERSION)..."
    
    # Remove existing installation if it exists
    if [[ -d "$INSTALL_DIR" ]]; then
        print_warning "Existing installation found at $INSTALL_DIR"
        read -p "Do you want to remove it and continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Removing existing installation..."
            rm -rf "$INSTALL_DIR"
        else
            print_error "Installation cancelled"
            exit 1
        fi
    fi
    
    # Clone the repository
    print_info "Cloning repository from branch: $VERSION"
    git clone --depth 1 --branch "$VERSION" "$REPO_URL.git" "$INSTALL_DIR"
    
    if [[ ! -d "$INSTALL_DIR" ]]; then
        print_error "Failed to download RuneCore Ecosystem"
        exit 1
    fi
    
    cd "$INSTALL_DIR"
    print_status "RuneCore Ecosystem downloaded successfully"
}

setup_environment() {
    print_info "Setting up RuneCore environment..."
    
    # Make scripts executable
    find . -name "*.sh" -type f -exec chmod +x {} \;
    
    # Create .env file if it doesn't exist
    if [[ ! -f ".env" ]]; then
        print_info "Creating environment configuration..."
        cat > .env << 'EOF'
# RuneCore AI Ecosystem Configuration
RUNECORE_VERSION=1.0.0
RUNECORE_ENV=production

# Service Ports
RUNECORE_CORE_PORT=11440
RUNECORE_CORE_INTERNAL_PORT=11441
RUNECORE_HA_PORT=11442
RUNEGUARD_LOGGER_PORT=5001
AI_BACKEND_PORT=5000
OLLAMA_WRAPPER_PORT=5002
ONNX_SERVICE_PORT=5006
FRONTEND_PORT=3000
CORE_MEMORY_PORT=5010
DASHBOARD_BACKEND_PORT=5004
DASHBOARD_FRONTEND_PORT=3001
MESH_DROP_PORT=5100
OLLAMA_PORT=11434

# Database Configuration
POSTGRES_DB=runecore_messages
POSTGRES_USER=runecore
POSTGRES_PASSWORD=runecore_secure_2024
DATABASE_URL=postgresql://runecore:runecore_secure_2024@postgres:5432/runecore_messages

# Security
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
RUNEGUARD_LOGGER_SECRET=your-runeguard-logger-secret-key

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Logging
LOG_LEVEL=INFO
EOF
        print_status "Environment configuration created"
    fi
    
    # Install Python dependencies if requirements.txt exists
    if [[ -f "requirements.txt" ]]; then
        print_info "Installing Python dependencies..."
        python3 -m pip install --user -r requirements.txt
    fi
    
    print_status "Environment setup completed"
}

install_runecore() {
    print_info "Installing RuneCore AI Ecosystem..."
    
    # Run the local install script if it exists
    if [[ -f "install.sh" ]]; then
        print_info "Running local installation script..."
        ./install.sh
    elif [[ -f "INSTALL.md" ]]; then
        print_info "Installation guide available in INSTALL.md"
    fi
    
    # Download any required models or dependencies
    if [[ -f "projects/RuneCore_AI/bootstrap/setup_models.py" ]]; then
        print_info "Setting up AI models..."
        cd projects/RuneCore_AI/bootstrap
        python3 setup_models.py
        cd "$INSTALL_DIR"
    fi
    
    print_status "RuneCore installation completed"
}

create_shortcuts() {
    print_info "Creating convenience shortcuts..."
    
    # Create a runecore command in user's local bin
    local bin_dir="$HOME/.local/bin"
    mkdir -p "$bin_dir"
    
    cat > "$bin_dir/runecore" << EOF
#!/bin/bash
# RuneCore AI Ecosystem Control Script

RUNECORE_DIR="$INSTALL_DIR"

case "\$1" in
    start)
        echo "🚀 Starting RuneCore AI Ecosystem..."
        cd "\$RUNECORE_DIR"
        if [[ -f "start_system.sh" ]]; then
            ./start_system.sh
        elif [[ -f "start_runecore_enhanced.sh" ]]; then
            ./start_runecore_enhanced.sh
        else
            echo "❌ No start script found"
            exit 1
        fi
        ;;
    stop)
        echo "🛑 Stopping RuneCore AI Ecosystem..."
        cd "\$RUNECORE_DIR"
        docker-compose down
        ;;
    status)
        echo "📊 RuneCore Service Status:"
        docker ps --filter "name=runecore"
        ;;
    logs)
        echo "📋 RuneCore Logs:"
        docker-compose logs -f
        ;;
    update)
        echo "🔄 Updating RuneCore..."
        cd "\$RUNECORE_DIR"
        git pull
        ;;
    uninstall)
        echo "🗑️ Uninstalling RuneCore..."
        curl -sSL "$RAW_URL/$VERSION/uninstall-runecore.sh" | bash
        ;;
    *)
        echo "RuneCore AI Ecosystem Control"
        echo "Usage: runecore {start|stop|status|logs|update|uninstall}"
        echo ""
        echo "Commands:"
        echo "  start      - Start all RuneCore services"
        echo "  stop       - Stop all RuneCore services"
        echo "  status     - Show service status"
        echo "  logs       - Show service logs"
        echo "  update     - Update to latest version"
        echo "  uninstall  - Remove RuneCore completely"
        ;;
esac
EOF
    
    chmod +x "$bin_dir/runecore"
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        print_info "Added $HOME/.local/bin to PATH (restart shell to use 'runecore' command)"
    fi
    
    print_status "Shortcuts created: 'runecore' command available"
}

show_completion() {
    print_header
    print_status "RuneCore AI Ecosystem installation completed!"
    echo ""
    print_info "Installation Details:"
    echo "  📁 Location: $INSTALL_DIR"
    echo "  🌿 Version: $VERSION"
    echo "  🐳 Docker: Ready"
    echo ""
    print_info "Quick Start:"
    echo "  cd $INSTALL_DIR"
    echo "  ./start_system.sh                    # Start all services"
    echo "  runecore start                       # Or use the convenience command"
    echo ""
    print_info "Service URLs (after starting):"
    echo "  🌐 Frontend:        http://localhost:3000"
    echo "  🧠 AI Service:      http://localhost:5000"
    echo "  🛡️ Error Logger:    http://localhost:5001"
    echo "  💬 Message Service: http://localhost:5003"
    echo ""
    print_info "Management Commands:"
    echo "  runecore status                      # Check service status"
    echo "  runecore logs                        # View logs"
    echo "  runecore stop                        # Stop services"
    echo "  runecore uninstall                   # Remove completely"
    echo ""
    print_warning "Don't forget to configure your .env file for production use!"
    echo ""
    print_status "Happy coding with RuneCore! 🚀"
}

delegate_uninstall() {
    # Reuse the sibling uninstall script. Prefer a local copy (when running from a
    # cloned repo); otherwise fetch it from GitHub as the generated CLI does.
    local uninstall_args=("--force" "--install-dir" "$INSTALL_DIR")
    if [[ "$PURGE" == "true" ]]; then
        uninstall_args+=("--purge")
    else
        uninstall_args+=("--keep-data")
    fi

    local local_script=""
    if [[ -f "$SCRIPT_DIR/uninstall-runecore.sh" ]]; then
        local_script="$SCRIPT_DIR/uninstall-runecore.sh"
    elif [[ -f "$INSTALL_DIR/uninstall-runecore.sh" ]]; then
        local_script="$INSTALL_DIR/uninstall-runecore.sh"
    fi

    if [[ -n "$local_script" ]]; then
        print_info "Running local uninstaller: $local_script"
        bash "$local_script" "${uninstall_args[@]}"
    else
        print_info "Fetching uninstaller from GitHub (branch: $VERSION)..."
        curl -sSL "$RAW_URL/$VERSION/uninstall-runecore.sh" | bash -s -- "${uninstall_args[@]}"
    fi
}

detect_existing_install() {
    # Returns 0 (true) if any trace of a prior RuneCore install is found.
    EXISTING_REASONS=()
    [[ -d "$INSTALL_DIR" ]] && EXISTING_REASONS+=("install directory $INSTALL_DIR")

    if command -v systemctl &> /dev/null; then
        if systemctl --user list-unit-files 2>/dev/null | grep -q '^runecore\.service'; then
            EXISTING_REASONS+=("systemd user service runecore.service")
        fi
    fi

    if command -v docker &> /dev/null; then
        local nets
        nets=$(docker network ls --format '{{.Name}}' 2>/dev/null             | grep -E '^(runecore_dev|runecore_ai_net|runecore_memory_net|runecore_dashboard_net)$' || true)
        [[ -n "$nets" ]] && EXISTING_REASONS+=("docker networks: $(echo "$nets" | tr '
' ' ')")

        local vols
        vols=$(docker volume ls --format '{{.Name}}' 2>/dev/null             | grep -E '(postgres_data|redis_data|influx_data|ollama_models|certs|runeguard_logs)' || true)
        [[ -n "$vols" ]] && EXISTING_REASONS+=("docker volumes present")

        local conts
        conts=$(docker ps -a --format '{{.Names}}' 2>/dev/null             | grep -E '(runecore|runeguard|runemesh|core_memory|ollama)' || true)
        [[ -n "$conts" ]] && EXISTING_REASONS+=("docker containers present")
    fi

    [[ ${#EXISTING_REASONS[@]} -gt 0 ]]
}

upgrade_existing_install() {
    # Idempotent re-run: clean upgrade of an existing install, preserving data
    # volumes and the existing .env file by default.
    print_warning "Existing RuneCore installation detected:"
    local reason
    for reason in "${EXISTING_REASONS[@]}"; do
        echo "    - $reason"
    done
    print_info "Performing a clean upgrade (preserving data volumes and .env)..."

    if [[ -d "$INSTALL_DIR" ]]; then
        cd "$INSTALL_DIR"

        if [[ -f "docker-compose.yml" ]] || [[ -f "docker-compose.dev.yml" ]]; then
            print_info "Stopping running services..."
            docker-compose down 2>/dev/null || true
        fi

        if [[ -d ".git" ]]; then
            print_info "Updating repository (branch: $VERSION)..."
            git fetch --depth 1 origin "$VERSION" 2>/dev/null || git fetch origin 2>/dev/null || true
            git checkout "$VERSION" 2>/dev/null || true
            git pull --ff-only 2>/dev/null || print_warning "Could not fast-forward; keeping local checkout"
        fi

        find . -name "*.sh" -type f -exec chmod +x {} \; 2>/dev/null || true
        if [[ -f ".env" ]]; then
            print_info "Existing .env preserved"
        fi

        if [[ -f "docker-compose.yml" ]]; then
            print_info "Rebuilding and restarting services..."
            docker-compose up -d --build 2>/dev/null || print_warning "Rebuild step skipped or failed; start manually with 'runecore start'"
        fi
    fi

    create_shortcuts
    print_status "RuneCore upgrade completed"
}

# Main installation flow
main() {
    print_header

    # Handle uninstall / reinstall actions by delegating to the sibling uninstaller.
    if [[ "$ACTION" == "uninstall" ]]; then
        print_info "Uninstalling RuneCore AI Ecosystem"
        [[ "$PURGE" == "true" ]] && print_warning "PURGE mode: data volumes and .env will be removed"
        delegate_uninstall
        exit 0
    fi

    if [[ "$ACTION" == "reinstall" ]]; then
        print_info "Reinstalling RuneCore AI Ecosystem"
        if [[ "$PURGE" == "true" ]]; then
            print_warning "PURGE mode: data volumes and .env will be removed before reinstall"
        else
            print_info "Data volumes and .env will be preserved across the reinstall"
        fi
        delegate_uninstall
    fi

    print_info "Installing RuneCore AI Ecosystem version: $VERSION"
    print_info "Installation directory: $INSTALL_DIR"
    echo ""

    check_requirements

    # Idempotent re-run: upgrade in place instead of failing or duplicating.
    # (Skipped for reinstall, which already cleaned up above.)
    if [[ "$ACTION" != "reinstall" ]] && detect_existing_install; then
        upgrade_existing_install
        show_completion
        exit 0
    fi

    download_runecore
    setup_environment
    install_runecore
    create_shortcuts
    show_completion
}

# Run main function
main "$@"
