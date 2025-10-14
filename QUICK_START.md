# 🚀 AI Service Platform - Quick Start

A comprehensive AI service platform with integrated error logging and a Discord-like chat interface.

## ⚡ Super Simple Startup

### One-Command Start

```bash
# Linux/WSL/macOS
./start_ai_service.sh

# Windows
start_ai_service.bat
```

That's it! The script will automatically:
- ✅ Check and activate the virtual environment
- ✅ Start ErrorLogger service (port 5001)
- ✅ Start AI Backend service (port 5000) 
- ✅ Start React Frontend (port 3000)
- ✅ Handle dependencies and environment setup

## 🛠️ First Time Setup

If you haven't set up the project yet:

```bash
# Install all dependencies
./install.sh

# Then start the services
./start_ai_service.sh
```

## 📋 Service Management

```bash
# Check service status
./start_ai_service.sh status

# Stop all services
./start_ai_service.sh stop

# Restart all services
./start_ai_service.sh restart

# Show help
./start_ai_service.sh help
```

## 🌐 Access Points

Once started, you can access:

- **Frontend (Main Interface)**: http://localhost:3000
- **Backend API**: http://localhost:5000
- **ErrorLogger Service**: http://localhost:5001

## 🔧 Advanced Options

### Manual Service Control

If you need to start services individually:

```bash
# Activate virtual environment first
source venv/bin/activate

# Start ErrorLogger
cd projects/ErrorLogger
python error_server.py --debug

# Start Backend (new terminal)
cd projects/ai_service/backend
python app.py --debug --skip-model-download

# Start Frontend (new terminal)  
cd projects/ai_service/frontend
npm start
```

### With Model Download

To enable AI model downloads (for actual inference):

```bash
# Edit the startup script or start backend manually
cd projects/ai_service/backend
python app.py --debug  # This will download models
```

## 🐛 Troubleshooting

### Check Logs

Each service creates its own log file:
- `projects/ErrorLogger/errorlogger.log`
- `projects/ai_service/backend/backend.log`
- `projects/ai_service/frontend/frontend.log`

### Common Issues

1. **Port already in use**: The script will detect and warn about conflicting processes
2. **Virtual environment missing**: Run `./install.sh` first
3. **npm not found**: Install Node.js for frontend functionality
4. **Model download issues**: Use `--skip-model-download` for testing

### Force Clean Start

```bash
# Stop all services
./start_ai_service.sh stop

# Kill any remaining processes
sudo killall python node npm || true

# Restart
./start_ai_service.sh start
```

## 🎯 What Each Service Does

- **ErrorLogger**: Centralized error logging and monitoring
- **Backend**: AI model management, inference API, model registry
- **Frontend**: React-based chat interface with Discord-like UI

## 📁 Project Structure

```
User_Functionality_WSL/
├── start_ai_service.sh    # 🚀 Main startup script (Linux/macOS)
├── start_ai_service.bat   # 🚀 Main startup script (Windows)
├── install.sh             # Setup and dependency installation
├── validate_deps.py       # Dependency validation
├── venv/                  # Virtual environment
├── projects/
│   ├── ErrorLogger/       # Error logging service
│   └── ai_service/        # AI platform
│       ├── backend/       # Flask API server
│       └── frontend/      # React chat interface
```

## 🔄 Environment Variables

The services use `.env` files for configuration:
- `projects/ai_service/backend/.env`
- `projects/ErrorLogger/.env`

These are automatically created during installation with sensible defaults.

---

**That's it! The startup script handles everything for you.** 🎉
