#!/bin/bash
# Frontend Development Server Startup Script
# Integrates with the modular ErrorLogger system

set -e

# Configuration
FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$FRONTEND_DIR/../.." && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"

# Service configuration
FRONTEND_PORT=3000
BACKEND_URL="http://127.0.0.1:5000"
ERRORLOGGER_URL="http://127.0.0.1:5001"

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
    local url="$1"
    if curl -s "$url/health" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Parse command line arguments
BUILD_ONLY=false
PRODUCTION=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --build-only)
            BUILD_ONLY=true
            shift
            ;;
        --production)
            PRODUCTION=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Start the React frontend development server"
            echo ""
            echo "Options:"
            echo "  --build-only    Build for production but don't start dev server"
            echo "  --production    Build for production and exit"
            echo "  --help          Show this help"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Cleanup function
cleanup() {
    if [[ -n "${DEV_SERVER_PID:-}" ]]; then
        log_info "Stopping React development server..."
        kill $DEV_SERVER_PID 2>/dev/null || true
    fi
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Main startup function
main() {
    log_info "🌐 Starting Frontend"
    echo
    
    # Check if Node.js is available
    if ! command -v node >/dev/null 2>&1; then
        log_error "Node.js is not installed. Please install Node.js first."
        exit 1
    fi
    
    if ! command -v npm >/dev/null 2>&1; then
        log_error "npm is not installed. Please install npm first."
        exit 1
    fi
    
    # Change to frontend directory
    cd "$FRONTEND_DIR"
    
    # Check if node_modules exists
    if [[ ! -d "node_modules" ]]; then
        log_info "Installing npm dependencies..."
        npm install
    fi
    
    # Check backend services
    if check_service "$BACKEND_URL"; then
        log_success "✅ Backend service is running"
    else
        log_warning "⚠️  Backend service not running at $BACKEND_URL"
        log_info "Please start the backend first:"
        log_info "cd $PROJECT_ROOT/projects/ai_service && ./start_ai_service.sh"
    fi
    
    if check_service "$ERRORLOGGER_URL"; then
        log_success "✅ ErrorLogger service is running"
    else
        log_warning "⚠️  ErrorLogger service not running at $ERRORLOGGER_URL"
        log_info "Please start ErrorLogger first:"
        log_info "cd $PROJECT_ROOT/projects/ErrorLogger && ./start_errorlogger.sh --background"
    fi
    
    # Set environment variables
    export REACT_APP_BACKEND_URL="$BACKEND_URL"
    export REACT_APP_ERRORLOGGER_URL="$ERRORLOGGER_URL"
    
    if [[ $PRODUCTION == true ]]; then
        log_info "Building for production..."
        npm run build
        log_success "Production build completed in: $FRONTEND_DIR/build"
        return 0
    fi
    
    if [[ $BUILD_ONLY == true ]]; then
        log_info "Building for production..."
        npm run build
        log_success "Build completed. Serve with backend or use: npx serve -s build"
        return 0
    fi
    
    # Start development server
    log_info "Starting React development server on port $FRONTEND_PORT..."
    echo
    log_info "Frontend will be available at: http://localhost:$FRONTEND_PORT"
    log_info "Backend proxy: $BACKEND_URL"
    echo
    log_info "Press Ctrl+C to stop..."
    echo
    
    # Start the development server
    PORT=$FRONTEND_PORT npm start &
    DEV_SERVER_PID=$!
    
    # Wait for the process
    wait $DEV_SERVER_PID
}

# Run main function
main "$@"
