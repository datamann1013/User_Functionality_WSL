#!/bin/bash
set -euo pipefail

# RuneCore Ecosystem - Distributed Installer
# One-file installer for complete RuneCore deployment
# Version: 1.0.0

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
GITHUB_REPO="datamann1013/RuneCore_Ecosystem"
REGISTRY="ghcr.io"
INSTALL_DIR="$HOME/.runecore"
DATA_DIR="$INSTALL_DIR/data"
CONFIG_DIR="$INSTALL_DIR/config"
LOG_DIR="$INSTALL_DIR/logs"

# Service configuration
SERVICES=("errorlogger" "backend" "frontend")
PORTS=("5001" "5000" "3000")
SERVICE_NAMES=("RuneGuard Security" "RuneMind Backend" "RuneMind Frontend")

# Utility functions
print_header() {
    echo -e "${PURPLE}"
    echo "╭─────────────────────────────────────────────────────────────╮"
    echo "│                    RUNECORE INSTALLER                       │"
    echo "│              Distributed AI Ecosystem Setup                │"
    echo "╰─────────────────────────────────────────────────────────────╯"
    echo -e "${NC}"
}

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_step() { echo -e "${CYAN}🔄 $1${NC}"; }

# System checks
check_system() {
    print_step "Checking system requirements..."
    
    # Check if running as root
    if [[ $EUID -eq 0 ]]; then
        print_error "Do not run this installer as root"
        exit 1
    fi
    
    # Check OS compatibility
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_success "Linux system detected"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        print_success "Windows/WSL system detected"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    
    # Check for required tools
    local required_tools=("curl" "docker" "docker-compose")
    local missing_tools=()
    
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        print_info "Please install the missing tools and run the installer again"
        
        # Provide installation hints
        if [[ "${missing_tools[*]}" == *"docker"* ]]; then
            echo ""
            print_info "Docker installation guide:"
            echo "  Ubuntu/Debian: sudo apt update && sudo apt install docker.io docker-compose"
            echo "  Arch Linux: sudo pacman -S docker docker-compose"
            echo "  WSL2: Install Docker Desktop for Windows"
            echo ""
            echo "  After installation, add your user to docker group:"
            echo "  sudo usermod -aG docker \$USER"
            echo "  Then log out and back in"
        fi
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker daemon is not running"
        print_info "Start Docker daemon with: sudo systemctl start docker"
        exit 1
    fi
    
    # Check Docker permissions
    if ! docker ps >/dev/null 2>&1; then
        print_error "Cannot access Docker daemon (permission denied)"
        print_info "Add your user to docker group: sudo usermod -aG docker \$USER"
        print_info "Then log out and back in"
        exit 1
    fi
    
    print_success "System requirements satisfied"
}

# Setup directories
setup_directories() {
    print_step "Setting up RuneCore directories..."
    
    mkdir -p "$INSTALL_DIR" "$DATA_DIR" "$CONFIG_DIR" "$LOG_DIR"
    mkdir -p "$DATA_DIR/ollama" "$DATA_DIR/guard" "$DATA_DIR/backend" 
    mkdir -p "$LOG_DIR/guard" "$LOG_DIR/backend" "$LOG_DIR/frontend"
    
    print_success "Directories created at $INSTALL_DIR"
}

# Download Docker Compose configuration
download_config() {
    print_step "Downloading RuneCore configuration..."
    
    local compose_url="https://raw.githubusercontent.com/$GITHUB_REPO/main/docker/docker-compose.prod.yml"
    
    if curl -fsSL "$compose_url" -o "$INSTALL_DIR/docker-compose.yml"; then
        print_success "Configuration downloaded"
    else
        print_error "Failed to download configuration from GitHub"
        print_info "Falling back to embedded configuration..."
        
        # Embedded fallback configuration
        cat > "$INSTALL_DIR/docker-compose.yml" << 'EOF'
version: '3.8'
services:
  ollama:
    image: ollama/ollama:latest
    container_name: runecore-ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ./data/ollama:/root/.ollama
    environment:
      - OLLAMA_ORIGINS=*
    networks:
      - runecore

  runeguard:
    image: ghcr.io/datamann1013/runecore_ecosystem-errorlogger:latest
    container_name: runecore-guard
    restart: unless-stopped
    ports:
      - "5001:5001"
    volumes:
      - ./logs/guard:/app/logs
      - ./data/guard:/app/data
    environment:
      - LOG_LEVEL=INFO
      - RUNECORE_MODE=production
    depends_on:
      - ollama
    networks:
      - runecore

  backend:
    image: ghcr.io/datamann1013/runecore_ecosystem-backend:latest
    container_name: runecore-backend
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./logs/backend:/app/logs
      - ./data/backend:/app/data
    environment:
      - OLLAMA_HOST=ollama:11434
      - ERRORLOGGER_URL=http://runeguard:5001
      - RUNECORE_MODE=production
    depends_on:
      - ollama
      - runeguard
    networks:
      - runecore

  frontend:
    image: ghcr.io/datamann1013/runecore_ecosystem-frontend:latest
    container_name: runecore-frontend
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:5000
      - REACT_APP_ERRORLOGGER_URL=http://localhost:5001
    depends_on:
      - backend
    networks:
      - runecore

networks:
  runecore:
    driver: bridge
    name: runecore-network
EOF
        print_success "Embedded configuration created"
    fi
}

# Pull Docker images
pull_images() {
    print_step "Pulling RuneCore Docker images..."
    
    local images=(
        "ollama/ollama:latest"
        "ghcr.io/$GITHUB_REPO-errorlogger:latest"
        "ghcr.io/$GITHUB_REPO-backend:latest"
        "ghcr.io/$GITHUB_REPO-frontend:latest"
    )
    
    for image in "${images[@]}"; do
        print_info "Pulling $image..."
        if docker pull "$image"; then
            print_success "✓ $image"
        else
            print_warning "Failed to pull $image (will try to build locally)"
        fi
    done
}

# Start services
start_services() {
    print_step "Starting RuneCore services..."
    
    cd "$INSTALL_DIR"
    
    # Stop any existing services
    docker-compose down 2>/dev/null || true
    
    # Start services
    if docker-compose up -d; then
        print_success "Services started successfully"
    else
        print_error "Failed to start services"
        return 1
    fi
}

# Health checks
check_services() {
    print_step "Performing health checks..."
    
    local max_attempts=30
    local attempt=1
    
    # Define service health check URLs
    local health_urls=(
        "http://localhost:11434/api/version"
        "http://localhost:5001/health"
        "http://localhost:5000/health"
        "http://localhost:3000"
    )
    
    local service_names=(
        "Ollama AI Service"
        "RuneGuard Security"
        "RuneMind Backend"
        "RuneMind Frontend"
    )
    
    for i in "${!health_urls[@]}"; do
        local url="${health_urls[$i]}"
        local name="${service_names[$i]}"
        
        print_info "Checking $name..."
        
        attempt=1
        while [[ $attempt -le $max_attempts ]]; do
            if curl -fsSL "$url" >/dev/null 2>&1; then
                print_success "$name is healthy"
                break
            fi
            
            if [[ $attempt -eq $max_attempts ]]; then
                print_warning "$name health check failed after $max_attempts attempts"
                break
            fi
            
            sleep 2
            ((attempt++))
        done
    done
}

# Setup AI models
setup_ai_models() {
    print_step "Setting up AI models..."
    
    print_info "Downloading recommended AI model (llama3.2:1b)..."
    
    # Wait for Ollama to be ready
    sleep 5
    
    if docker exec runecore-ollama ollama pull llama3.2:1b; then
        print_success "AI model downloaded successfully"
    else
        print_warning "Failed to download AI model (you can do this later)"
        print_info "To download models later, run:"
        print_info "  docker exec runecore-ollama ollama pull llama3.2:1b"
    fi
}

# Create management script
create_management_script() {
    print_step "Creating management script..."
    
    cat > "$INSTALL_DIR/runecore" << 'EOF'
#!/bin/bash
# RuneCore Management Script

INSTALL_DIR="$HOME/.runecore"
cd "$INSTALL_DIR"

case "$1" in
    start)
        echo "Starting RuneCore services..."
        docker-compose up -d
        ;;
    stop)
        echo "Stopping RuneCore services..."
        docker-compose down
        ;;
    restart)
        echo "Restarting RuneCore services..."
        docker-compose restart
        ;;
    status)
        echo "RuneCore service status:"
        docker-compose ps
        ;;
    logs)
        service="${2:-}"
        if [[ -n "$service" ]]; then
            docker-compose logs -f "$service"
        else
            docker-compose logs -f
        fi
        ;;
    update)
        echo "Updating RuneCore images..."
        docker-compose pull
        docker-compose up -d
        ;;
    uninstall)
        echo "Uninstalling RuneCore..."
        docker-compose down -v
        docker rmi $(docker images | grep runecore | awk '{print $3}') 2>/dev/null || true
        rm -rf "$INSTALL_DIR"
        echo "RuneCore uninstalled"
        ;;
    *)
        echo "RuneCore Management Commands:"
        echo "  start       - Start all services"
        echo "  stop        - Stop all services"
        echo "  restart     - Restart all services"
        echo "  status      - Show service status"
        echo "  logs [svc]  - Show logs (optionally for specific service)"
        echo "  update      - Update to latest images"
        echo "  uninstall   - Remove RuneCore completely"
        ;;
esac
EOF
    
    chmod +x "$INSTALL_DIR/runecore"
    
    # Add to PATH if not already there
    if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
        echo 'export PATH="$HOME/.runecore:$PATH"' >> "$HOME/.bashrc"
        print_info "Added RuneCore to PATH (restart shell or source ~/.bashrc)"
    fi
    
    print_success "Management script created at $INSTALL_DIR/runecore"
}

# Print final information
print_completion_info() {
    echo ""
    echo -e "${GREEN}🎉 RuneCore Installation Complete! 🎉${NC}"
    echo ""
    echo -e "${CYAN}📋 Service URLs:${NC}"
    echo "  • RuneMind AI Interface:  http://localhost:3000"
    echo "  • AI Backend API:         http://localhost:5000"
    echo "  • Security Dashboard:     http://localhost:5001"
    echo "  • Ollama AI Service:      http://localhost:11434"
    echo ""
    echo -e "${CYAN}🛠️ Management Commands:${NC}"
    echo "  • Start services:    $INSTALL_DIR/runecore start"
    echo "  • Stop services:     $INSTALL_DIR/runecore stop"
    echo "  • View status:       $INSTALL_DIR/runecore status"
    echo "  • View logs:         $INSTALL_DIR/runecore logs"
    echo "  • Update system:     $INSTALL_DIR/runecore update"
    echo ""
    echo -e "${CYAN}📁 Installation Directory:${NC} $INSTALL_DIR"
    echo ""
    echo -e "${YELLOW}💡 Next Steps:${NC}"
    echo "  1. Visit http://localhost:3000 to access RuneMind AI"
    echo "  2. Test the AI with: curl -X POST http://localhost:5000/api/ai/chat -H 'Content-Type: application/json' -d '{\"message\":\"Hello RuneCore!\"}'"
    echo "  3. Check system status at http://localhost:5001"
    echo ""
    echo -e "${GREEN}Welcome to the RuneCore Ecosystem! 🚀${NC}"
}

# Main installation flow
main() {
    print_header
    
    echo -e "${BLUE}This installer will set up the complete RuneCore ecosystem using Docker.${NC}"
    echo -e "${BLUE}The following services will be installed:${NC}"
    echo "  • Ollama AI Service (Local AI models)"
    echo "  • RuneGuard Security (Error monitoring & security)"
    echo "  • RuneMind Backend (AI processing & API)"
    echo "  • RuneMind Frontend (Web interface)"
    echo ""
    
    read -p "Continue with installation? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Installation cancelled"
        exit 0
    fi
    
    # Run installation steps
    check_system
    setup_directories
    download_config
    pull_images
    start_services
    check_services
    setup_ai_models
    create_management_script
    print_completion_info
    
    echo ""
    print_success "Installation completed successfully!"
}

# Error handling
trap 'echo -e "\n${RED}Installation interrupted!${NC}"; exit 1' INT TERM

# Run main function
main "$@"
