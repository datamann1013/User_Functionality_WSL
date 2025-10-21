#!/bin/bash

# RuneCore AI Ecosystem Arch Linux Installer
# Usage: curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/install-runecore-arch.sh | bash
# Or: curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/install-runecore-arch.sh | bash -s -- --version=AI_service

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Default configuration
REPO_URL="https://github.com/datamann1013/RuneCore_Ecosystem"
RAW_URL="https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem"
DEFAULT_VERSION="main"
INSTALL_DIR="$HOME/RuneCore_Ecosystem"
VERSION=""
USE_AUR=false

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
        --use-aur)
            USE_AUR=true
            shift
            ;;
        --help|-h)
            echo "RuneCore AI Ecosystem Arch Linux Installer"
            echo ""
            echo "Usage: curl -sSL $RAW_URL/main/install-runecore-arch.sh | bash [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --version=VERSION     Version/branch to install (default: main)"
            echo "  --install-dir=DIR     Installation directory (default: $HOME/RuneCore_Ecosystem)"
            echo "  --use-aur            Use AUR packages when available"
            echo "  --help               Show this help message"
            echo ""
            echo "Available versions:"
            echo "  main                 Latest stable release"
            echo "  AI_service          AI service development branch"
            echo "  experimental        Experimental features"
            echo "  test                Testing branch"
            echo ""
            echo "Examples:"
            echo "  # Install latest stable"
            echo "  curl -sSL $RAW_URL/main/install-runecore-arch.sh | bash"
            echo ""
            echo "  # Install AI service branch with AUR packages"
            echo "  curl -sSL $RAW_URL/AI_service/install-runecore-arch.sh | bash -s -- --version=AI_service --use-aur"
            echo ""
            echo "  # Install to custom directory"
            echo "  curl -sSL $RAW_URL/AI_service/install-runecore-arch.sh | bash -s -- --install-dir=/opt/runecore"
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
    echo "║                       Arch Linux Edition                     ║"
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

print_arch() {
    echo -e "${PURPLE}🏛️  $1${NC}"
}

check_arch_linux() {
    if [[ ! -f /etc/arch-release ]]; then
        print_error "This installer is specifically for Arch Linux"
        print_info "For other distributions, use: install-runecore-remote.sh"
        exit 1
    fi
    
    print_arch "Detected Arch Linux - proceeding with optimized installation"
}

check_aur_helper() {
    local aur_helpers=("yay" "paru" "pikaur" "trizen")
    local found_helper=""
    
    if [[ "$USE_AUR" == "true" ]]; then
        for helper in "${aur_helpers[@]}"; do
            if command -v "$helper" &> /dev/null; then
                found_helper="$helper"
                break
            fi
        done
        
        if [[ -n "$found_helper" ]]; then
            print_arch "Found AUR helper: $found_helper"
            AUR_HELPER="$found_helper"
        else
            print_warning "No AUR helper found, will use pacman only"
            print_info "Consider installing yay or paru for better AUR support"
            USE_AUR=false
        fi
    fi
}

install_arch_dependencies() {
    print_arch "Installing Arch Linux dependencies..."
    
    # Update package database
    print_info "Updating package database..."
    sudo pacman -Sy --noconfirm
    
    # Essential packages
    local essential_packages=(
        "git"
        "docker"
        "docker-compose"
        "python"
        "python-pip"
        "curl"
        "wget"
        "base-devel"
    )
    
    print_info "Installing essential packages with pacman..."
    sudo pacman -S --needed --noconfirm "${essential_packages[@]}"
    
    # Optional AUR packages for enhanced experience
    if [[ "$USE_AUR" == "true" && -n "$AUR_HELPER" ]]; then
        print_arch "Installing AUR packages for enhanced experience..."
        
        local aur_packages=(
            "docker-desktop"
            "visual-studio-code-bin"
            "postman-bin"
        )
        
        for package in "${aur_packages[@]}"; do
            if ! pacman -Qi "$package" &> /dev/null; then
                print_info "Installing $package from AUR..."
                $AUR_HELPER -S --noconfirm "$package" || print_warning "Failed to install $package from AUR"
            fi
        done
    fi
    
    print_status "Arch dependencies installed"
}

setup_arch_services() {
    print_arch "Setting up Arch Linux services..."
    
    # Enable and start Docker
    print_info "Configuring Docker service..."
    sudo systemctl enable docker.service
    sudo systemctl start docker.service
    
    # Add user to docker group
    if ! groups $USER | grep -q docker; then
        print_info "Adding user to docker group..."
        sudo usermod -aG docker $USER
        print_warning "You may need to log out and back in for docker group changes to take effect"
    fi
    
    # Check if Docker is working
    if docker info &> /dev/null; then
        print_status "Docker service is running and accessible"
    else
        print_warning "Docker is installed but may require a logout/login to access"
    fi
}

check_requirements() {
    print_info "Checking Arch Linux system requirements..."
    
    # Check for required commands
    local required_commands=("git" "docker" "docker-compose" "curl" "python3")
    local missing_commands=()
    
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            # Special case for python3 on Arch (it's usually just 'python')
            if [[ "$cmd" == "python3" ]] && command -v python &> /dev/null; then
                continue
            fi
            missing_commands+=("$cmd")
        fi
    done
    
    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        print_error "Missing required commands: ${missing_commands[*]}"
        print_arch "Installing missing dependencies..."
        install_arch_dependencies
    else
        print_status "All requirements satisfied"
    fi
    
    setup_arch_services
}

create_arch_systemd_service() {
    print_arch "Creating systemd user service for RuneCore..."
    
    local service_dir="$HOME/.config/systemd/user"
    mkdir -p "$service_dir"
    
    cat > "$service_dir/runecore.service" << EOF
[Unit]
Description=RuneCore AI Ecosystem
After=docker.service
Requires=docker.service

[Service]
Type=forking
WorkingDirectory=$INSTALL_DIR
ExecStart=/bin/bash -c 'cd $INSTALL_DIR && ./start_system.sh'
ExecStop=/bin/bash -c 'cd $INSTALL_DIR && docker-compose down'
Restart=on-failure
RestartSec=10
User=$USER
Group=docker

[Install]
WantedBy=default.target
EOF
    
    # Reload systemd and enable the service
    systemctl --user daemon-reload
    print_info "RuneCore systemd service created (not enabled by default)"
    print_info "To enable auto-start: systemctl --user enable runecore.service"
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

setup_arch_environment() {
    print_arch "Setting up Arch Linux optimized environment..."
    
    # Make scripts executable
    find . -name "*.sh" -type f -exec chmod +x {} \;
    
    # Create Arch-specific .env file
    if [[ ! -f ".env" ]]; then
        print_info "Creating Arch Linux optimized environment configuration..."
        cat > .env << 'EOF'
# RuneCore AI Ecosystem Configuration - Arch Linux
RUNECORE_VERSION=1.0.0
RUNECORE_ENV=production
RUNECORE_OS=arch

# Service Ports
AI_SERVICE_PORT=5000
ERRORLOGGER_PORT=5001
MESSAGE_SERVICE_PORT=5003
FRONTEND_PORT=3000
OLLAMA_PORT=11434

# Database Configuration
POSTGRES_DB=runecore_messages
POSTGRES_USER=runecore
POSTGRES_PASSWORD=runecore_secure_2024
DATABASE_URL=postgresql://runecore:runecore_secure_2024@postgres:5432/runecore_messages

# Security
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
ERRORLOGGER_SECRET=your-errorlogger-secret-key

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Arch Linux specific paths
RUNECORE_DATA_PATH=/home/$USER/.local/share/runecore
RUNECORE_LOG_PATH=/home/$USER/.local/share/runecore/logs
RUNECORE_CACHE_PATH=/home/$USER/.cache/runecore

# Performance optimizations for Arch
DOCKER_BUILDKIT=1
COMPOSE_DOCKER_CLI_BUILD=1

# Logging
LOG_LEVEL=INFO
EOF
        print_status "Arch Linux optimized environment configuration created"
    fi
    
    # Create data directories
    mkdir -p "$HOME/.local/share/runecore/logs"
    mkdir -p "$HOME/.cache/runecore"
    
    # Install Python dependencies with user install
    if [[ -f "requirements.txt" ]]; then
        print_info "Installing Python dependencies..."
        python -m pip install --user -r requirements.txt
    fi
    
    print_status "Arch environment setup completed"
}

install_runecore() {
    print_info "Installing RuneCore AI Ecosystem on Arch Linux..."
    
    # Run the local install script if it exists
    if [[ -f "install.sh" ]]; then
        print_info "Running local installation script..."
        ./install.sh
    elif [[ -f "INSTALL.md" ]]; then
        print_info "Installation guide available in INSTALL.md"
    fi
    
    # Download any required models or dependencies
    if [[ -f "projects/ai_service/bootstrap/setup_models.py" ]]; then
        print_info "Setting up AI models..."
        cd projects/ai_service/bootstrap
        python setup_models.py
        cd "$INSTALL_DIR"
    fi
    
    create_arch_systemd_service
    print_status "RuneCore installation completed"
}

create_arch_shortcuts() {
    print_arch "Creating Arch Linux shortcuts and commands..."
    
    # Create a runecore command in user's local bin
    local bin_dir="$HOME/.local/bin"
    mkdir -p "$bin_dir"
    
    cat > "$bin_dir/runecore" << EOF
#!/bin/bash
# RuneCore AI Ecosystem Control Script - Arch Linux

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
        docker ps --filter "name=ai_service"
        systemctl --user is-active runecore.service 2>/dev/null && echo "systemd service: active" || echo "systemd service: inactive"
        ;;
    logs)
        echo "📋 RuneCore Logs:"
        cd "\$RUNECORE_DIR"
        docker-compose logs -f
        ;;
    service)
        case "\$2" in
            enable)
                systemctl --user enable runecore.service
                echo "✅ RuneCore systemd service enabled"
                ;;
            disable)
                systemctl --user disable runecore.service
                echo "✅ RuneCore systemd service disabled"
                ;;
            start)
                systemctl --user start runecore.service
                echo "✅ RuneCore systemd service started"
                ;;
            stop)
                systemctl --user stop runecore.service
                echo "✅ RuneCore systemd service stopped"
                ;;
            *)
                echo "Usage: runecore service {enable|disable|start|stop}"
                ;;
        esac
        ;;
    update)
        echo "🔄 Updating RuneCore..."
        cd "\$RUNECORE_DIR"
        git pull
        ;;
    uninstall)
        echo "🗑️ Uninstalling RuneCore..."
        curl -sSL "https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/$VERSION/uninstall-runecore-arch.sh" | bash
        ;;
    *)
        echo "RuneCore AI Ecosystem Control - Arch Linux"
        echo "Usage: runecore {start|stop|status|logs|service|update|uninstall}"
        echo ""
        echo "Commands:"
        echo "  start         - Start all RuneCore services"
        echo "  stop          - Stop all RuneCore services"
        echo "  status        - Show service status"
        echo "  logs          - Show service logs"
        echo "  service       - Manage systemd service (enable|disable|start|stop)"
        echo "  update        - Update to latest version"
        echo "  uninstall     - Remove RuneCore completely"
        echo ""
        echo "Arch Linux specific:"
        echo "  runecore service enable    - Enable auto-start with systemd"
        echo "  runecore service start     - Start via systemd"
        ;;
esac
EOF
    
    chmod +x "$bin_dir/runecore"
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        if [[ -f "$HOME/.zshrc" ]]; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc"
        fi
        print_info "Added $HOME/.local/bin to PATH (restart shell to use 'runecore' command)"
    fi
    
    print_status "Arch Linux shortcuts created: 'runecore' command available"
}

show_arch_completion() {
    print_header
    print_status "RuneCore AI Ecosystem installation completed on Arch Linux!"
    echo ""
    print_arch "Installation Details:"
    echo "  📁 Location: $INSTALL_DIR"
    echo "  🌿 Version: $VERSION"
    echo "  🐳 Docker: Ready"
    echo "  🏛️ OS: Arch Linux"
    echo "  ⚙️ Systemd: Service created"
    echo ""
    print_info "Quick Start:"
    echo "  cd $INSTALL_DIR"
    echo "  ./start_system.sh                    # Start all services"
    echo "  runecore start                       # Or use the convenience command"
    echo ""
    print_arch "Arch Linux Specific Features:"
    echo "  runecore service enable              # Auto-start with systemd"
    echo "  runecore service start               # Start via systemd"
    echo "  systemctl --user status runecore    # Check systemd status"
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
    print_arch "Welcome to RuneCore on Arch Linux! 🏛️🚀"
}

# Main installation flow
main() {
    print_header
    print_arch "Installing RuneCore AI Ecosystem on Arch Linux"
    print_info "Version: $VERSION"
    print_info "Installation directory: $INSTALL_DIR"
    if [[ "$USE_AUR" == "true" ]]; then
        print_info "AUR packages: Enabled"
    fi
    echo ""
    
    check_arch_linux
    check_aur_helper
    check_requirements
    download_runecore
    setup_arch_environment
    install_runecore
    create_arch_shortcuts
    show_arch_completion
}

# Run main function
main "$@"
