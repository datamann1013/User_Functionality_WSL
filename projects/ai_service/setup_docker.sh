#!/bin/bash
# AI Service Docker Setup Script
# Installs Docker and sets up the complete containerized environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to detect Linux distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo $ID
    elif [ -f /etc/arch-release ]; then
        echo "arch"
    elif [ -f /etc/debian_version ]; then
        echo "debian"
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    else
        echo "unknown"
    fi
}

echo -e "${BLUE}🐳 AI Service Docker Setup${NC}"
echo "=================================="
echo ""

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo -e "${RED}❌ Please run this script as a regular user, not root${NC}"
    echo "   Docker installation will handle sudo requirements"
    exit 1
fi

# Detect system information
DISTRO=$(detect_distro)
echo -e "${BLUE}🖥️  System Information:${NC}"
echo "   Distribution: $DISTRO"
echo "   User: $USER"
echo "   Shell: $SHELL"
echo ""

# Configuration
AI_SERVICE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$AI_SERVICE_DIR/../.." && pwd)"

echo -e "${YELLOW}📁 Project Structure:${NC}"
echo "   AI Service Dir: $AI_SERVICE_DIR"
echo "   Project Root:   $PROJECT_ROOT"
echo ""

# Function to install Docker based on distribution
install_docker() {
    echo -e "${YELLOW}🔧 Installing Docker...${NC}"
    
    DISTRO=$(detect_distro)
    echo -e "${BLUE}📋 Detected OS: $DISTRO${NC}"
    
    case $DISTRO in
        "arch"|"manjaro")
            install_docker_arch
            ;;
        "ubuntu"|"debian"|"pop"|"linuxmint"|"kali")
            install_docker_debian
            ;;
        "fedora"|"rhel"|"centos")
            install_docker_redhat
            ;;
        *)
            echo -e "${RED}❌ Unsupported distribution: $DISTRO${NC}"
            echo -e "${YELLOW}💡 Please install Docker manually from: https://docs.docker.com/engine/install/${NC}"
            exit 1
            ;;
    esac
}

# Install Docker on Arch Linux
install_docker_arch() {
    echo -e "${BLUE}🏹 Installing Docker on Arch Linux...${NC}"
    
    # Update package database
    sudo pacman -Sy
    
    # Install Docker
    sudo pacman -S --noconfirm docker docker-compose
    
    # Create docker group if it doesn't exist
    sudo groupadd -f docker
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    # Enable and start Docker service
    sudo systemctl enable docker.service
    sudo systemctl enable containerd.service
    sudo systemctl start docker.service
    
    echo -e "${GREEN}✅ Docker installed successfully on Arch Linux${NC}"
}

# Install Docker on Debian/Ubuntu
install_docker_debian() {
    echo -e "${BLUE}🐧 Installing Docker on Debian/Ubuntu/Kali...${NC}"
    
    # Update package list
    sudo apt-get update
    
    # Install prerequisites
    sudo apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    sudo mkdir -p /etc/apt/keyrings
    
    # Determine which repository to use
    DISTRO=$(detect_distro)
    if [[ "$DISTRO" == "kali" ]]; then
        # Use Debian repository for Kali
        curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        echo \
            "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
            bullseye stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    else
        # Use Ubuntu repository for Ubuntu/derivatives
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        echo \
            "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
            $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    fi
    
    # Install Docker Engine
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    echo -e "${GREEN}✅ Docker installed successfully on Debian/Ubuntu/Kali${NC}"
}

# Install Docker on Red Hat/Fedora
install_docker_redhat() {
    echo -e "${BLUE}🎩 Installing Docker on Red Hat/Fedora...${NC}"
    
    # Install Docker using dnf/yum
    if command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y docker docker-compose
    else
        sudo yum install -y docker docker-compose
    fi
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    # Enable and start Docker
    sudo systemctl enable docker
    sudo systemctl start docker
    
    echo -e "${GREEN}✅ Docker installed successfully on Red Hat/Fedora${NC}"
}

# Function to check Docker installation
check_docker() {
    if command -v docker >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Docker is installed${NC}"
        docker --version
        
        # Check if Docker daemon is running
        if ! docker info >/dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Docker daemon is not running - starting...${NC}"
            sudo systemctl start docker 2>/dev/null || sudo service docker start 2>/dev/null || {
                echo -e "${RED}❌ Failed to start Docker daemon${NC}"
                echo -e "${YELLOW}💡 Try running: sudo systemctl start docker${NC}"
                return 1
            }
        fi
        
        # Check docker group
        if groups $USER | grep -q docker; then
            echo -e "${GREEN}✅ User is in docker group${NC}"
            
            # Test Docker access
            if docker ps >/dev/null 2>&1; then
                echo -e "${GREEN}✅ Docker is working correctly${NC}"
                return 0
            else
                echo -e "${YELLOW}⚠️  Docker group membership not active - please log out and back in${NC}"
                return 1
            fi
        else
            echo -e "${YELLOW}⚠️  User not in docker group - adding now${NC}"
            
            # Create docker group if it doesn't exist
            sudo groupadd -f docker 2>/dev/null || true
            
            # Add user to docker group
            sudo usermod -aG docker $USER
            
            echo -e "${YELLOW}⚠️  Please log out and log back in, then run this script again${NC}"
            echo -e "${BLUE}💡 Or try: newgrp docker${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ Docker not found - installing...${NC}"
        install_docker
        echo -e "${YELLOW}⚠️  Docker installed. Please log out and log back in, then run this script again${NC}"
        echo -e "${BLUE}💡 Or try: newgrp docker && ./setup_docker.sh${NC}"
        return 1
    fi
}

# Function to setup environment
setup_environment() {
    echo -e "${YELLOW}🔧 Setting up environment...${NC}"
    
    # Create necessary directories
    mkdir -p "$AI_SERVICE_DIR/logs"
    mkdir -p "$AI_SERVICE_DIR/uploads"
    mkdir -p "$PROJECT_ROOT/logs"
    
    # Create .env file if it doesn't exist
    if [ ! -f "$AI_SERVICE_DIR/.env" ]; then
        cat > "$AI_SERVICE_DIR/.env" << EOF
# AI Service Environment Configuration
# Generated on $(date)

# Database
DATABASE_URL=postgresql://ai_user:ai_secure_pass_2025@postgres:5432/ai_service
POSTGRES_DB=ai_service
POSTGRES_USER=ai_user
POSTGRES_PASSWORD=ai_secure_pass_2025

# Redis
REDIS_URL=redis://:redis_secure_2025@redis:6379/0
REDIS_PASSWORD=redis_secure_2025

# Authentication
JWT_SECRET_KEY=jwt_super_secure_key_2025_change_in_production
ENCRYPTION_KEY=$(head -c 32 /dev/urandom | base64)

# Services
ERRORLOGGER_URL=http://errorlogger:5001/log
OLLAMA_SERVICE_URL=http://ollama_service:5002
OLLAMA_HOST=http://host.docker.internal:11434

# Flask
FLASK_ENV=production
FLASK_DEBUG=false

# Ports
BACKEND_PORT=5000
FRONTEND_PORT=3000
OLLAMA_SERVICE_PORT=5002
ERRORLOGGER_PORT=5001
POSTGRES_PORT=5432
REDIS_PORT=6379
EOF
        echo -e "${GREEN}✅ Created .env file${NC}"
    else
        echo -e "${YELLOW}ℹ️  .env file already exists${NC}"
    fi
    
    echo -e "${GREEN}✅ Environment setup complete${NC}"
    echo ""
}

# Function to start services
start_services() {
    echo -e "${YELLOW}🚀 Starting AI Service Platform...${NC}"
    
    cd "$AI_SERVICE_DIR"
    
    # Pull images and build
    echo -e "${BLUE}📦 Building Docker images...${NC}"
    docker compose build --no-cache
    
    echo -e "${BLUE}🚀 Starting services...${NC}"
    docker compose up -d
    
    echo -e "${BLUE}📊 Service status:${NC}"
    docker compose ps
    
    echo ""
    echo -e "${GREEN}🎉 AI Service Platform started successfully!${NC}"
    echo ""
    echo -e "${BLUE}📍 Service URLs:${NC}"
    echo "   🎨 Frontend:     http://localhost:3000"
    echo "   🤖 Backend API:  http://localhost:5000"
    echo "   🔧 Ollama:       http://localhost:5002"
    echo "   📊 ErrorLogger:  http://localhost:5001"
    echo "   🗄️  PostgreSQL:   localhost:5432"
    echo "   💾 Redis:        localhost:6379"
    echo ""
    echo -e "${YELLOW}💡 Next steps:${NC}"
    echo "   1. Wait for all services to be healthy (check with: docker compose ps)"
    echo "   2. Visit http://localhost:3000 to access the frontend"
    echo "   3. Check logs with: docker compose logs -f [service_name]"
    echo ""
}

# Function to show logs
show_logs() {
    echo -e "${BLUE}📋 Recent logs from all services:${NC}"
    cd "$AI_SERVICE_DIR"
    docker compose logs --tail=10
}

# Main execution
main() {
    # Check Docker installation
    if ! check_docker; then
        echo -e "${YELLOW}🔄 Please log out and log back in, then run this script again${NC}"
        exit 0
    fi
    
    # Setup environment
    setup_environment
    
    # Check if services are already running
    cd "$AI_SERVICE_DIR"
    if docker compose ps | grep -q "Up"; then
        echo -e "${YELLOW}ℹ️  Services are already running${NC}"
        docker compose ps
        echo ""
        echo -e "${BLUE}Available commands:${NC}"
        echo "   docker compose down     # Stop all services"
        echo "   docker compose up -d    # Start all services"
        echo "   docker compose logs -f  # Follow logs"
        echo "   docker compose ps       # Show status"
        echo ""
        read -p "Do you want to restart the services? [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}🔄 Restarting services...${NC}"
            docker compose down
            start_services
        fi
    else
        # Start services
        start_services
    fi
    
    # Show recent logs
    echo -e "${BLUE}📋 Checking service health...${NC}"
    sleep 5
    show_logs
}

# Script help
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    echo "AI Service Docker Setup Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --help, -h     Show this help message"
    echo "  --logs         Show service logs only"
    echo "  --stop         Stop all services"
    echo "  --restart      Restart all services"
    echo ""
    echo "This script will:"
    echo "  1. Install Docker if not present"
    echo "  2. Set up the AI Service environment"
    echo "  3. Build and start all containers"
    echo "  4. Show service status and URLs"
    exit 0
fi

# Handle specific commands
case "$1" in
    "--logs")
        cd "$AI_SERVICE_DIR"
        docker compose logs -f
        ;;
    "--stop")
        cd "$AI_SERVICE_DIR"
        docker compose down
        echo -e "${GREEN}✅ Services stopped${NC}"
        ;;
    "--restart")
        cd "$AI_SERVICE_DIR"
        docker compose down
        start_services
        ;;
    *)
        main
        ;;
esac
