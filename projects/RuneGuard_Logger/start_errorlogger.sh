#!/bin/bash
# ErrorLogger Service Startup Script
# Standalone service for modular architecture

set -e

# Configuration
ERRORLOGGER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$ERRORLOGGER_DIR/../.." && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"

# Service configuration
SERVICE_URL="http://127.0.0.1:5001"
DEFAULT_PORT=5001

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
    if curl -s "$SERVICE_URL/health" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Parse command line arguments
PORT=$DEFAULT_PORT
BACKGROUND=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --background|-bg)
            BACKGROUND=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --port PORT       Port to run on (default: $DEFAULT_PORT)"
            echo "  --background      Run in background"
            echo "  --help            Show this help"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Update service URL with custom port
SERVICE_URL="http://127.0.0.1:$PORT"

# Cleanup function
cleanup() {
    if [[ -n "${SERVICE_PID:-}" ]] && [[ $BACKGROUND == false ]]; then
        log_info "Stopping ErrorLogger service..."
        kill $SERVICE_PID 2>/dev/null || true
    fi
}

# Set trap for cleanup (only if not running in background)
if [[ $BACKGROUND == false ]]; then
    trap cleanup EXIT INT TERM
fi

# Main startup function
main() {
    log_info "🚀 Starting ErrorLogger Service"
    echo
    
    # Check if already running
    if check_service; then
        log_error "ErrorLogger service is already running on port $PORT"
        log_info "Stop it first or use a different port with --port"
        exit 1
    fi
    
    # Check if virtual environment exists
    if [[ ! -d "$VENV_DIR" ]]; then
        log_error "Virtual environment not found at: $VENV_DIR"
        log_info "Please run: python -m venv $VENV_DIR"
        exit 1
    fi
    
    # Activate virtual environment
    log_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    
    # Install/update dependencies
    log_info "Checking dependencies..."
    pip install -q -r "$ERRORLOGGER_DIR/requirements.txt"
    
    # Set environment variables
    export FLASK_ENV="development"
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    
    # Start ErrorLogger service
    log_info "Starting ErrorLogger service on port $PORT..."
    cd "$ERRORLOGGER_DIR"
    
    if [[ $BACKGROUND == true ]]; then
        # Start in background
        nohup python error_logger_service.py --port $PORT --host 127.0.0.1 > errorlogger.log 2>&1 &
        SERVICE_PID=$!
        echo $SERVICE_PID > errorlogger.pid
        
        # Wait a moment and check if it started successfully
        sleep 2
        if check_service; then
            log_success "🎉 ErrorLogger service started in background!"
            log_info "  Service URL: $SERVICE_URL"
            log_info "  Health Check: $SERVICE_URL/health"
            log_info "  PID: $SERVICE_PID (saved to errorlogger.pid)"
            log_info "  Logs: $ERRORLOGGER_DIR/errorlogger.log"
            echo
            log_info "To stop: kill $SERVICE_PID"
        else
            log_error "Failed to start ErrorLogger service"
            exit 1
        fi
    else
        # Start in foreground
        python error_logger_service.py --port $PORT --host 127.0.0.1 &
        SERVICE_PID=$!
        
        # Wait for service to be ready
        log_info "Waiting for service to be ready..."
        for i in {1..30}; do
            if check_service; then
                log_success "✅ ErrorLogger service is ready!"
                break
            fi
            sleep 1
        done
        
        if check_service; then
            echo
            log_success "🎉 ErrorLogger Service is running!"
            echo
            log_info "Service Information:"
            log_info "  Service URL:   $SERVICE_URL"
            log_info "  Health Check:  $SERVICE_URL/health"
            log_info "  Log Endpoint:  $SERVICE_URL/log"
            log_info "  Recent Logs:   $SERVICE_URL/logs/recent"
            log_info "  Services:      $SERVICE_URL/services"
            echo
            log_info "Test the service:"
            log_info "  curl $SERVICE_URL/health"
            log_info "  curl -X POST $SERVICE_URL/log -H 'Content-Type: application/json' -d '{\"error_code\":\"TEST\",\"message\":\"Test message\",\"service\":\"test\"}'"
            echo
            
            # Keep running until interrupted
            log_info "Press Ctrl+C to stop..."
            wait $SERVICE_PID
        else
            log_error "Failed to start ErrorLogger service"
            exit 1
        fi
    fi
}

# Run main function
main "$@"
