#!/bin/bash

# RuneCore AI Ecosystem Uninstaller
# Usage: curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore.sh | bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default configuration
DEFAULT_INSTALL_DIR="$HOME/RuneCore_Ecosystem"
INSTALL_DIR="$DEFAULT_INSTALL_DIR"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --install-dir=*)
            INSTALL_DIR="${1#*=}"
            shift
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --force)
            FORCE_UNINSTALL=true
            shift
            ;;
        --help|-h)
            echo "RuneCore AI Ecosystem Uninstaller"
            echo ""
            echo "Usage: curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore.sh | bash [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --install-dir=DIR     RuneCore installation directory (default: $HOME/RuneCore_Ecosystem)"
            echo "  --force              Skip confirmation prompts"
            echo "  --help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  # Standard uninstall"
            echo "  curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore.sh | bash"
            echo ""
            echo "  # Force uninstall without prompts"
            echo "  curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore.sh | bash -s -- --force"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                RuneCore AI Ecosystem Uninstaller             ║"
    echo "║                                                              ║"
    echo "║          🗑️ Removing RuneCore Installation Safely            ║"
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

confirm_uninstall() {
    if [[ "$FORCE_UNINSTALL" == "true" ]]; then
        return 0
    fi
    
    print_warning "This will remove RuneCore AI Ecosystem and all its data!"
    print_info "Installation directory: $INSTALL_DIR"
    echo ""
    print_info "The following will be removed:"
    echo "  📁 All RuneCore files and directories"
    echo "  🐳 RuneCore Docker containers and images"
    echo "  📊 RuneCore Docker volumes (databases, logs)"
    echo "  🔗 RuneCore command shortcuts"
    echo "  ⚙️ RuneCore configuration files"
    echo ""
    print_warning "Docker itself and other Docker containers will NOT be removed"
    echo ""
    
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Uninstall cancelled"
        exit 0
    fi
}

stop_services() {
    print_info "Stopping RuneCore services..."
    
    # Stop using docker-compose if available
    if [[ -f "$INSTALL_DIR/docker-compose.yml" ]] || [[ -f "$INSTALL_DIR/docker/docker-compose.prod.yml" ]]; then
        cd "$INSTALL_DIR"
        if [[ -f "docker-compose.yml" ]]; then
            docker-compose down -v --remove-orphans 2>/dev/null || true
        fi
        if [[ -f "docker/docker-compose.prod.yml" ]]; then
            docker-compose -f docker/docker-compose.prod.yml down -v --remove-orphans 2>/dev/null || true
        fi
    fi
    
    # Stop and remove RuneCore containers
    print_info "Removing RuneCore containers..."
    docker ps -a --filter "name=ai_service" --filter "name=runecore" --filter "name=errorlogger" --filter "name=message_service" -q | xargs -r docker rm -f
    
    # Remove RuneCore Docker networks
    print_info "Removing RuneCore networks..."
    docker network ls --filter "name=ai_service" --filter "name=runecore" -q | xargs -r docker network rm 2>/dev/null || true
    
    print_status "Services stopped"
}

remove_docker_images() {
    print_info "Removing RuneCore Docker images..."
    
    # Remove RuneCore-specific images
    docker images --filter "reference=ai_service*" --filter "reference=runecore*" --filter "reference=errorlogger*" --filter "reference=message_service*" -q | xargs -r docker rmi -f 2>/dev/null || true
    
    # Remove dangling images
    docker image prune -f >/dev/null 2>&1 || true
    
    print_status "Docker images removed"
}

remove_docker_volumes() {
    print_info "Removing RuneCore Docker volumes..."
    
    # Remove RuneCore-specific volumes
    docker volume ls --filter "name=ai_service" --filter "name=runecore" --filter "name=postgres" --filter "name=redis" -q | xargs -r docker volume rm 2>/dev/null || true
    
    # Remove dangling volumes
    docker volume prune -f >/dev/null 2>&1 || true
    
    print_status "Docker volumes removed"
}

remove_files() {
    print_info "Removing RuneCore files..."
    
    # Remove main installation directory
    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
        print_status "Removed installation directory: $INSTALL_DIR"
    fi
    
    # Remove runecore command
    if [[ -f "$HOME/.local/bin/runecore" ]]; then
        rm -f "$HOME/.local/bin/runecore"
        print_status "Removed runecore command"
    fi
    
    # Remove any RuneCore-specific configuration
    local config_dirs=(
        "$HOME/.runecore"
        "$HOME/.config/runecore"
    )
    
    for config_dir in "${config_dirs[@]}"; do
        if [[ -d "$config_dir" ]]; then
            rm -rf "$config_dir"
            print_status "Removed configuration directory: $config_dir"
        fi
    done
    
    # Remove RuneCore-specific environment files
    local env_files=(
        "$HOME/.runecore_env"
        "$HOME/.env.runecore"
    )
    
    for env_file in "${env_files[@]}"; do
        if [[ -f "$env_file" ]]; then
            rm -f "$env_file"
            print_status "Removed environment file: $env_file"
        fi
    done
}

cleanup_python_packages() {
    print_info "Checking for RuneCore Python packages..."
    
    # List of RuneCore-specific packages that might have been installed
    local runecore_packages=(
        "runecore"
        "runecore-ai"
        "runecore-errorlogger"
    )
    
    for package in "${runecore_packages[@]}"; do
        if python3 -m pip show "$package" >/dev/null 2>&1; then
            print_info "Removing Python package: $package"
            python3 -m pip uninstall -y "$package" 2>/dev/null || true
        fi
    done
    
    print_status "Python package cleanup completed"
}

cleanup_system_services() {
    print_info "Checking for RuneCore system services..."
    
    # Check for systemd services
    local service_files=(
        "/etc/systemd/system/runecore.service"
        "/etc/systemd/system/runecore-ai.service"
        "/etc/systemd/system/runecore-errorlogger.service"
        "$HOME/.config/systemd/user/runecore.service"
    )
    
    for service_file in "${service_files[@]}"; do
        if [[ -f "$service_file" ]]; then
            print_info "Removing systemd service: $service_file"
            sudo rm -f "$service_file" 2>/dev/null || rm -f "$service_file" 2>/dev/null || true
        fi
    done
    
    # Reload systemd if we removed any services
    if systemctl --user daemon-reload 2>/dev/null; then
        print_status "Reloaded user systemd services"
    fi
    
    if sudo systemctl daemon-reload 2>/dev/null; then
        print_status "Reloaded system systemd services"
    fi
}

show_completion() {
    print_header
    print_status "RuneCore AI Ecosystem has been completely removed!"
    echo ""
    print_info "What was removed:"
    echo "  ✅ All RuneCore files and directories"
    echo "  ✅ RuneCore Docker containers and images"
    echo "  ✅ RuneCore Docker volumes and networks"
    echo "  ✅ RuneCore command shortcuts"
    echo "  ✅ RuneCore configuration files"
    echo "  ✅ RuneCore Python packages"
    echo "  ✅ RuneCore system services"
    echo ""
    print_info "What was preserved:"
    echo "  ✅ Docker Engine and Docker Compose"
    echo "  ✅ Other Docker containers and images"
    echo "  ✅ System Python installation"
    echo "  ✅ User data not related to RuneCore"
    echo ""
    print_warning "Your system is clean and ready for a fresh RuneCore installation if needed"
    echo ""
    print_info "To reinstall RuneCore:"
    echo "  curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/install-runecore-remote.sh | bash"
    echo ""
    print_status "Thank you for using RuneCore AI Ecosystem! 👋"
}

# Main uninstall flow
main() {
    print_header
    print_info "RuneCore AI Ecosystem Uninstaller"
    print_info "Installation directory: $INSTALL_DIR"
    echo ""
    
    confirm_uninstall
    
    print_info "Starting uninstall process..."
    
    stop_services
    remove_docker_images
    remove_docker_volumes
    remove_files
    cleanup_python_packages
    cleanup_system_services
    
    show_completion
}

# Run main function
main "$@"
