#!/bin/bash
"""
Main System Startup Script
Modular Architecture - Start ErrorLogger and AI Service
"""

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

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

# Parse command line arguments
START_ERRORLOGGER=true
START_AI_SERVICE=true
BACKGROUND=false

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo "Start the modular system with ErrorLogger and AI Service"
    echo ""
    echo "Options:"
    echo "  --no-errorlogger  Don't start ErrorLogger service"
    echo "  --no-ai-service   Don't start AI Service"
    echo "  --errorlogger-only Start only ErrorLogger service"
    echo "  --ai-service-only Start only AI Service"
    echo "  --background      Start services in background"
    echo "  --help            Show this help"
    echo ""
    echo "Examples:"
    echo "  $0                      # Start both services"
    echo "  $0 --errorlogger-only   # Start only ErrorLogger"
    echo "  $0 --ai-service-only    # Start only AI Service"
    echo "  $0 --background         # Start both in background"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-errorlogger)
            START_ERRORLOGGER=false
            shift
            ;;
        --no-ai-service)
            START_AI_SERVICE=false
            shift
            ;;
        --errorlogger-only)
            START_ERRORLOGGER=true
            START_AI_SERVICE=false
            shift
            ;;
        --ai-service-only)
            START_ERRORLOGGER=false
            START_AI_SERVICE=true
            shift
            ;;
        --background|-bg)
            BACKGROUND=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Cleanup function
cleanup() {
    log_info "Shutting down services..."
    
    # Kill background processes if any
    if [[ -f "$PROJECT_ROOT/projects/ErrorLogger/errorlogger.pid" ]]; then
        PID=$(cat "$PROJECT_ROOT/projects/ErrorLogger/errorlogger.pid" 2>/dev/null || echo "")
        if [[ -n "$PID" ]]; then
            kill $PID 2>/dev/null || true
            rm -f "$PROJECT_ROOT/projects/ErrorLogger/errorlogger.pid"
            log_info "Stopped ErrorLogger service"
        fi
    fi
    
    # Additional cleanup can be added here
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Check virtual environment
check_venv() {
    if [[ ! -d "$PROJECT_ROOT/venv" ]]; then
        log_error "Virtual environment not found at: $PROJECT_ROOT/venv"
        log_info "Please run: python -m venv $PROJECT_ROOT/venv"
        log_info "Then activate and install dependencies"
        exit 1
    fi
}

# Start ErrorLogger service
start_errorlogger() {
    log_info "🔧 Starting ErrorLogger Service..."
    
    if [[ $BACKGROUND == true ]]; then
        cd "$PROJECT_ROOT/projects/ErrorLogger"
        ./start_errorlogger.sh --background
    else
        log_info "Starting ErrorLogger in background for system setup..."
        cd "$PROJECT_ROOT/projects/ErrorLogger"
        ./start_errorlogger.sh --background
        
        # Wait for it to be ready
        sleep 3
        if curl -s "http://127.0.0.1:5001/health" >/dev/null 2>&1; then
            log_success "✅ ErrorLogger service is ready"
        else
            log_warning "⚠️  ErrorLogger service may not be ready"
        fi
    fi
}

# Start AI Service
start_ai_service() {
    log_info "🤖 Starting AI Service..."
    
    cd "$PROJECT_ROOT/projects/ai_service"
    if [[ $BACKGROUND == true ]]; then
        log_info "Background mode not implemented for AI Service yet"
        log_info "Starting in foreground mode..."
    fi
    ./start_ai_service.sh
}

# Main function
main() {
    log_info "🚀 Starting Modular System"
    echo
    
    # Check virtual environment
    check_venv
    
    if [[ $START_ERRORLOGGER == true ]] && [[ $START_AI_SERVICE == true ]]; then
        log_info "Starting both ErrorLogger and AI Service..."
        start_errorlogger
        sleep 2  # Give ErrorLogger time to start
        start_ai_service
    elif [[ $START_ERRORLOGGER == true ]]; then
        log_info "Starting ErrorLogger service only..."
        start_errorlogger
        if [[ $BACKGROUND == false ]]; then
            log_info "ErrorLogger started. Press Ctrl+C to stop."
            # Keep script running
            while true; do
                sleep 1
            done
        fi
    elif [[ $START_AI_SERVICE == true ]]; then
        log_info "Starting AI Service only..."
        start_ai_service
    else
        log_error "No services selected to start!"
        show_help
        exit 1
    fi
}

# Run main function
main "$@"
