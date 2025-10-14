# AI Service - Simple Prototype

A minimal, working prototype of an AI chat service with React frontend, Flask backend, and centralized error logging.

## 🚀 Quick Start

```bash
# Start the complete prototype (all services)
./start_prototype.sh
```

This will start:
- **ErrorLogger** service (port 5001) - Centralized logging
- **Backend** service (port 5000) - Flask API with mock AI responses  
- **React Frontend** (port 3000) - Simple chat interface

## 🏗️ Architecture

```
Frontend (React) :3000
    ↓ API calls
Backend (Flask) :5000  
    ↓ Error logging
ErrorLogger :5001
```

### Components

1. **Frontend** (`projects/ai_service/frontend/`)
   - Simple React app with chat interface
   - Connects to backend API
   - Logs errors to centralized service

2. **Backend** (`projects/ai_service/backend/app.py`)
   - Flask server with chat API
   - Mock AI responses for demonstration
   - Forwards frontend errors to ErrorLogger

3. **ErrorLogger** (`projects/ErrorLogger/error_logger_service.py`)
   - Standalone logging service
   - Used by all components
   - JSON logs with daily rotation

## 🛠️ Development

### Individual Services

```bash
# ErrorLogger only
cd projects/ErrorLogger
./start_errorlogger.sh --background

# Backend only (requires ErrorLogger running)
cd projects/ai_service/backend
source ../../venv/bin/activate
python app.py

# Frontend only (requires Backend running)
cd projects/ai_service/frontend
npm start
```

### Testing

```bash
# Test backend API
curl http://localhost:5000/health
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello!"}'

# Test ErrorLogger
curl http://localhost:5001/health
curl http://localhost:5001/logs/recent
```

## 📝 What's Next

This is a minimal prototype ready for expansion:

- **Add real AI models** (replace mock responses)
- **Improve frontend UI** (add more features)
- **Add authentication** (user management)
- **Database integration** (chat history)
- **More service types** (leverage modular ErrorLogger)

## 🎯 Key Features

- ✅ **Simple codebase** - Easy to understand and modify
- ✅ **Modular design** - ErrorLogger serves multiple services
- ✅ **Real-time chat** - Working chat interface
- ✅ **Error tracking** - Centralized logging from all components
- ✅ **Development ready** - Hot reload, easy testing
- ✅ **Production capable** - Can build and deploy

The codebase is intentionally minimal so you can learn and extend it step by step!
