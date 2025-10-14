# User Functionality WSL - Modular System

A modular system with AI Service and ErrorLogger components designed for efficient development workflows.

## Architecture

### Modular Design
- **ErrorLogger**: Standalone centralized logging service that can be used by multiple programs
- **AI Service**: Backend service that connects to ErrorLogger for monitoring and debugging
- **Clean Separation**: Each service can run independently and connect to existing services

### Components

#### ErrorLogger Service (`projects/ErrorLogger/`)
- Centralized logging service for multiple applications
- HTTP API for logging events, errors, and monitoring
- Daily log file rotation with JSON formatting
- Service registration and filtering capabilities

#### AI Service (`projects/ai_service/`)
- Flask-based backend with mock AI responses (demonstration mode)
- Connects to existing ErrorLogger service for logging
- REST API for chat, inference, and model management
- Health checks and service status monitoring

## Quick Start

### 1. Setup Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Start the System
```bash
# Start both services
./start_system.sh

# Start only ErrorLogger
./start_system.sh --errorlogger-only

# Start only AI Service (ErrorLogger should be running)
./start_system.sh --ai-service-only

# Start services in background
./start_system.sh --background
```

### 3. Individual Service Control

#### ErrorLogger Service
```bash
cd projects/ErrorLogger
./start_errorlogger.sh                    # Foreground
./start_errorlogger.sh --background       # Background
./start_errorlogger.sh --port 5002        # Custom port
```

#### AI Service
```bash
cd projects/ai_service
./start_ai_service.sh
```

## API Endpoints

### ErrorLogger Service (Port 5001)
- `GET /health` - Health check
- `POST /log` - Log an event/error
- `GET /logs/recent` - Get recent logs
- `GET /services` - List registered services

### AI Service (Port 5000)
- `GET /health` - Health check with ErrorLogger status
- `GET /api/models` - List available models
- `POST /api/chat` - Chat interface
- `POST /api/inference` - Direct model inference

## Testing

### Test ErrorLogger
```bash
# Health check
curl http://127.0.0.1:5001/health

# Log a test message
curl -X POST http://127.0.0.1:5001/log \
  -H "Content-Type: application/json" \
  -d '{"error_code":"TEST","message":"Test message","service":"test"}'

# Get recent logs
curl http://127.0.0.1:5001/logs/recent
```

### Test AI Service
```bash
# Health check
curl http://127.0.0.1:5000/health

# Chat test
curl -X POST http://127.0.0.1:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello!"}'

# List models
curl http://127.0.0.1:5000/api/models
```

## Configuration

### Environment Variables
- `ERRORLOGGER_SERVICE_URL`: URL for ErrorLogger service (default: http://127.0.0.1:5001/log)
- `FLASK_ENV`: Flask environment (development/production)

### Files
- `projects/ErrorLogger/.env`: ErrorLogger configuration
- `projects/ai_service/backend/.env`: AI Service configuration

## Dependencies

### ErrorLogger Service
- Flask >= 2.3.0
- python-dotenv >= 1.0.0

### AI Service
- Flask >= 2.3.0
- requests >= 2.31.0
- python-dotenv >= 1.0.0
- psutil >= 5.9.0

## Development Notes

### Modular Philosophy
- ErrorLogger runs as standalone service
- Multiple applications can connect to the same ErrorLogger
- AI Service detects and uses existing ErrorLogger if available
- Services fail gracefully if dependencies are unavailable

### Current State
- AI Service runs in demonstration mode with mock responses
- Ready for real AI model integration
- Comprehensive logging and monitoring infrastructure

### Next Steps
- Integrate real AI models (transformers, local models, APIs)
- Add authentication and security
- Implement frontend interface
- Add more service types to the modular system
