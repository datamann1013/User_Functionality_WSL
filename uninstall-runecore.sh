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
KEEP_DATA=false
ENV_BACKUP_FILE="$HOME/.runecore.env.backup"

# Data volumes preserved with --keep-data (databases, models, certs, logs)
PRESERVED_VOLUME_PATTERN='postgres_data|pgdata|redis_data|influx_data|ollama_models|ollama_data|onnx_models|certs|runeguard_logs|backups'
# Current-generation RuneCore resource name prefixes
RUNECORE_VOLUME_PATTERN='^(runecore|runeguard|runemesh|core_memory)|^ollama_models$'

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
        --keep-data)
            KEEP_DATA=true
            shift
            ;;
        --purge)
            KEEP_DATA=false
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
            echo "  --keep-data          Preserve data volumes (postgres, redis, influx, ollama models,"
            echo "                       certs, runeguard logs) and back up .env to $HOME/.runecore.env.backup"
            echo "  --purge              Full wipe including data volumes (default behavior)"
            echo "  --help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  # Standard uninstall (removes everything)"
            echo "  curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore.sh | bash"
            echo ""
            echo "  # Force uninstall without prompts"
            echo "  curl -sSL https://raw.githubusercontent.com/datamann1013/RuneCore_Ecosystem/main/uninstall-runecore.sh | bash -s -- --force"
            echo ""
            echo "  # Uninstall but keep databases / models / certs (for later reinstall)"
            echo "  bash uninstall-runecore.sh --keep-data"
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

    if [[ "$KEEP_DATA" == "true" ]]; then
        print_warning "This will remove RuneCore AI Ecosystem (data volumes will be PRESERVED)!"
    else
        print_warning "This will remove RuneCore AI Ecosystem and all its data!"
    fi
    print_info "Installation directory: $INSTALL_DIR"
    echo ""
    print_info "The following will be removed:"
    echo "  📁 All RuneCore files and directories"
    echo "  🐳 RuneCore Docker containers and images"
    if [[ "$KEEP_DATA" == "true" ]]; then
        echo "  📊 RuneCore Docker volumes (EXCEPT databases, models, certs, logs)"
    else
        echo "  📊 RuneCore Docker volumes (databases, logs)"
    fi
    echo "  🔗 RuneCore command shortcuts"
    echo "  ⚙️ RuneCore configuration files"
    echo ""
    print_warning "Docker itself and other Docker containers will NOT be removed"
    echo ""

    # Fix for piped input from curl - redirect from /dev/tty
    if [[ -t 0 ]]; then
        # Interactive terminal
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Uninstall cancelled"
            exit 0
        fi
    else
        # Piped input - try to read from terminal directly
        print_warning "Script is running from pipe (curl). Attempting to read from terminal..."
        exec < /dev/tty
        read -p "Are you sure you want to continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Uninstall cancelled"
            exit 0
        fi
    fi
}

backup_env_file() {
    if [[ "$KEEP_DATA" == "true" && -f "$INSTALL_DIR/.env" ]]; then
        cp "$INSTALL_DIR/.env" "$ENV_BACKUP_FILE"
        print_status "Backed up .env to $ENV_BACKUP_FILE"
    fi
}

stop_services() {
    print_info "Stopping RuneCore services..."

    # docker-compose down flags: only remove volumes on full wipe
    local down_flags="--remove-orphans"
    if [[ "$KEEP_DATA" != "true" ]]; then
        down_flags="-v --remove-orphans"
    fi

    # Stop using docker-compose for all known compose files
    if [[ -d "$INSTALL_DIR" ]]; then
        cd "$INSTALL_DIR"
        local compose_files=(
            "docker-compose.yml"
            "docker/docker-compose.prod.yml"
            "docker/docker-compose.unified.yml"
        )
        # Per-module dev stacks (RuneCore_AI, RuneCore_Core, RuneCore_Memory, RuneGuard_*, RuneMesh_Drop, ...)
        for dev_compose in projects/*/docker-compose.dev.yml; do
            [[ -f "$dev_compose" ]] && compose_files+=("$dev_compose")
        done
        for compose_file in "${compose_files[@]}"; do
            if [[ -f "$compose_file" ]]; then
                docker-compose -f "$compose_file" down $down_flags 2>/dev/null || true
            fi
        done
    fi

    # Stop and remove RuneCore containers (current generation names)
    print_info "Removing RuneCore containers..."
    docker ps -a --filter "name=runecore" --filter "name=runeguard" --filter "name=dashboard_backend" --filter "name=dashboard_frontend" --filter "name=mesh_drop" --filter "name=core_memory" -q | xargs -r docker rm -f 2>/dev/null || true

    # Remove RuneCore Docker networks (runecore_dev, runecore_ai_net, runecore_memory_net, runecore_dashboard_net)
    print_info "Removing RuneCore networks..."
    docker network ls --filter "name=runecore" -q | xargs -r docker network rm 2>/dev/null || true

    print_status "Services stopped"
}

remove_docker_images() {
    print_info "Removing RuneCore Docker images..."

    # Remove RuneCore-specific images (runecore_*, runecore-*, runeguard_*, runemesh_*)
    docker images --filter "reference=runecore*" --filter "reference=runeguard*" --filter "reference=runemesh*" --filter "reference=core_memory*" -q | xargs -r docker rmi -f 2>/dev/null || true

    # Remove dangling images
    docker image prune -f >/dev/null 2>&1 || true

    print_status "Docker images removed"
}

remove_docker_volumes() {
    if [[ "$KEEP_DATA" == "true" ]]; then
        print_info "Removing RuneCore Docker volumes (preserving data volumes)..."
    else
        print_info "Removing RuneCore Docker volumes..."
    fi

    # Remove RuneCore-specific volumes by exact name (avoids deleting other projects' postgres/redis volumes)
    local volumes
    volumes=$(docker volume ls --format '{{.Name}}' 2>/dev/null | grep -E "$RUNECORE_VOLUME_PATTERN" || true)
    for vol in $volumes; do
        if [[ "$KEEP_DATA" == "true" ]] && echo "$vol" | grep -qE "$PRESERVED_VOLUME_PATTERN"; then
            print_info "Preserving data volume: $vol"
            continue
        fi
        docker volume rm "$vol" 2>/dev/null || true
    done

    # Remove dangling volumes (only on full wipe)
    if [[ "$KEEP_DATA" != "true" ]]; then
        docker volume prune -f >/dev/null 2>&1 || true
    fi

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

    if [[ "$KEEP_DATA" == "true" ]]; then
        print_info "Preserving configuration directories (--keep-data)"
        return 0
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
        "$ENV_BACKUP_FILE"
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
        "runecore-runeguard-logger"
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
        "/etc/systemd/system/runecore-runeguard-logger.service"
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
    print_status "RuneCore AI Ecosystem has been removed!"
    echo ""
    print_info "What was removed:"
    echo "  ✅ All RuneCore files and directories"
    echo "  ✅ RuneCore Docker containers and images"
    echo "  ✅ RuneCore Docker networks"
    echo "  ✅ RuneCore command shortcuts"
    echo "  ✅ RuneCore Python packages"
    echo "  ✅ RuneCore system services"
    echo ""
    print_info "What was preserved:"
    echo "  ✅ Docker Engine and Docker Compose"
    echo "  ✅ Other Docker containers and images"
    echo "  ✅ System Python installation"
    echo "  ✅ User data not related to RuneCore"
    if [[ "$KEEP_DATA" == "true" ]]; then
        echo "  ✅ RuneCore data volumes (postgres, redis, influx, ollama models, certs, logs)"
        echo "  ✅ .env backup at $ENV_BACKUP_FILE"
    fi
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
    if [[ "$KEEP_DATA" == "true" ]]; then
        print_info "Mode: keep-data (data volumes and .env preserved)"
    fi
    echo ""

    confirm_uninstall

    print_info "Starting uninstall process..."

    backup_env_file
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
