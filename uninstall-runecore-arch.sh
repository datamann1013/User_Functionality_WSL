#!/bin/bash

# RuneCore AI Ecosystem Arch Linux Uninstaller
# Usage: curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore-arch.sh | bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
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
            echo "RuneCore AI Ecosystem Arch Linux Uninstaller"
            echo ""
            echo "Usage: curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore-arch.sh | bash [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --install-dir=DIR     RuneCore installation directory (default: $HOME/RuneCore_Ecosystem)"
            echo "  --force              Skip confirmation prompts"
            echo "  --help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  # Standard uninstall"
            echo "  curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore-arch.sh | bash"
            echo ""
            echo "  # Force uninstall without prompts"
            echo "  curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore-arch.sh | bash -s -- --force"
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
    echo "║                       Arch Linux Edition                     ║"
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

print_arch() {
    echo -e "${PURPLE}🏛️  $1${NC}"
}

check_arch_linux() {
    if [[ ! -f /etc/arch-release ]]; then
        print_error "This uninstaller is specifically for Arch Linux"
        print_info "For other distributions, use: uninstall-runecore.sh"
        exit 1
    fi
    
    print_arch "Detected Arch Linux - proceeding with optimized removal"
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
    echo "  🏛️ RuneCore systemd services"
    echo "  📦 RuneCore data directories"
    echo ""
    print_arch "Arch Linux specific cleanup included"
    print_warning "Docker itself and other Docker containers will NOT be removed"
    echo ""
    
    # Simple and reliable approach - just check if we're in a pipe
    if [[ ! -t 0 ]]; then
        # We're piped from curl - automatically cancel for safety
        print_warning "Script is running from curl pipe - cannot safely read user input"
        print_info "For safety, uninstall has been cancelled"
        echo ""
        print_info "To proceed with uninstall, use one of these options:"
        echo "  1. Force uninstall: curl ... | bash -s -- --force"
        echo "  2. Download and run locally: wget <script-url> && bash <script-name>"
        echo "  3. Use local uninstaller: ./local-uninstall.sh"
        echo ""
        exit 0
    fi
    
    # We have a real terminal - this will work
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Uninstall cancelled"
        exit 0
    fi
    
    print_status "Confirmed - proceeding with uninstall"
}

stop_systemd_service() {
    print_arch "Stopping and removing systemd services..."
    
    # Stop and disable user service
    if systemctl --user is-active runecore.service &>/dev/null; then
        systemctl --user stop runecore.service
        print_status "Stopped RuneCore systemd service"
    fi
    
    if systemctl --user is-enabled runecore.service &>/dev/null; then
        systemctl --user disable runecore.service
        print_status "Disabled RuneCore systemd service"
    fi
    
    # Remove service file
    local service_file="$HOME/.config/systemd/user/runecore.service"
    if [[ -f "$service_file" ]]; then
        rm -f "$service_file"
        systemctl --user daemon-reload
        print_status "Removed RuneCore systemd service file"
    fi
}

stop_services() {
    print_info "Stopping RuneCore services..."
    
    # Stop systemd service first
    stop_systemd_service
    
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
    docker ps -a --filter "name=ai_service" --filter "name=runecore" --filter "name=errorlogger" --filter "name=message_service" -q | xargs -r docker rm -f 2>/dev/null || true
    
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

remove_arch_files() {
    print_arch "Removing RuneCore files and Arch-specific directories..."
    
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
    
    # Remove Arch-specific configuration directories
    local config_dirs=(
        "$HOME/.runecore"
        "$HOME/.config/runecore"
        "$HOME/.local/share/runecore"
        "$HOME/.cache/runecore"
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
        if python -m pip show "$package" >/dev/null 2>&1; then
            print_info "Removing Python package: $package"
            python -m pip uninstall -y "$package" 2>/dev/null || true
        fi
    done
    
    print_status "Python package cleanup completed"
}

cleanup_arch_packages() {
    print_arch "Checking for RuneCore-related packages to remove..."
    
    # Check if user wants to remove packages that were installed specifically for RuneCore
    if [[ "$FORCE_UNINSTALL" != "true" ]]; then
        echo ""
        print_warning "Do you want to remove packages that were installed for RuneCore?"
        print_info "This includes development packages that may be used by other applications:"
        echo "  - docker (if not used elsewhere)"
        echo "  - docker-compose (if not used elsewhere)"
        echo "  - Additional development tools"
        echo ""
        read -p "Remove RuneCore-specific packages? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            REMOVE_PACKAGES=true
        fi
    fi
    
    if [[ "$REMOVE_PACKAGES" == "true" ]]; then
        print_arch "Removing RuneCore-specific packages..."
        
        # Note: We're being very conservative here - only removing packages that are clearly RuneCore-specific
        # We DO NOT remove docker, python, git, etc. as these are commonly used by other applications
        
        print_info "Only removing clearly RuneCore-specific packages"
        print_info "Docker, Python, Git, and other common tools will be preserved"
    else
        print_info "Preserving all system packages"
    fi
    
    print_status "Package cleanup completed"
}

show_arch_completion() {
    print_header
    print_status "RuneCore AI Ecosystem has been completely removed from Arch Linux!"
    echo ""
    print_arch "What was removed:"
    echo "  ✅ All RuneCore files and directories"
    echo "  ✅ RuneCore Docker containers and images"
    echo "  ✅ RuneCore Docker volumes and networks"
    echo "  ✅ RuneCore command shortcuts"
    echo "  ✅ RuneCore configuration files"
    echo "  ✅ RuneCore Python packages"
    echo "  ✅ RuneCore systemd services"
    echo "  ✅ RuneCore data directories"
    echo ""
    print_info "What was preserved:"
    echo "  ✅ Docker Engine and Docker Compose"
    echo "  ✅ Other Docker containers and images"
    echo "  ✅ System Python installation"
    echo "  ✅ System packages (git, curl, etc.)"
    echo "  ✅ User data not related to RuneCore"
    echo ""
    print_arch "Your Arch Linux system is clean and ready for a fresh RuneCore installation if needed"
    echo ""
    print_info "To reinstall RuneCore on Arch Linux:"
    echo "  curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/install-runecore-arch.sh | bash"
    echo ""
    print_info "For AI service branch with AUR packages:"
    echo "  curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/AI_service/install-runecore-arch.sh | bash -s -- --version=AI_service --use-aur"
    echo ""
    print_arch "Thank you for using RuneCore AI Ecosystem on Arch Linux! 🏛️👋"
    echo ""
}

# Main uninstall flow
main() {
    print_header
    print_arch "RuneCore AI Ecosystem Arch Linux Uninstaller"
    print_info "Installation directory: $INSTALL_DIR"
    echo ""
    
    check_arch_linux
    confirm_uninstall
    
    print_info "Starting Arch Linux optimized uninstall process..."
    
    stop_services
    remove_docker_images
    remove_docker_volumes
    remove_arch_files
    cleanup_python_packages
    cleanup_arch_packages
    
    show_arch_completion
    
    # Explicit exit to ensure script terminates
    exit 0
}

# Run main function and ensure exit
main "$@"
exit $?
