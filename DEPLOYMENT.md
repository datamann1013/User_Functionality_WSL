# Three-Server Configuration Guide

The AI Service runs as 3 separate servers that can be deployed independently:

## 🖥️ Single Machine (Default)

```bash
./start_prototype.sh
```

## 🌐 Multiple Machines

### Machine 1 - ErrorLogger Server
```bash
cd projects/ErrorLogger
source ../../venv/bin/activate
python error_logger_service.py --port 5001 --host 0.0.0.0
```

### Machine 2 - Backend Server
```bash
cd projects/ai_service/backend
source ../../../venv/bin/activate
export ERRORLOGGER_SERVICE_URL="http://MACHINE1_IP:5001/log"
python app.py --port 5000 --host 0.0.0.0
```

### Machine 3 - Frontend Server
```bash
cd projects/ai_service/frontend
export REACT_APP_BACKEND_URL="http://MACHINE2_IP:5000"
npm start
```

## 🔧 Environment Variables

You can customize ports and URLs:

```bash
# Custom ports
export ERRORLOGGER_PORT=5001
export BACKEND_PORT=5000  
export FRONTEND_PORT=3000

# Remote services
export ERRORLOGGER_SERVICE_URL="http://remote-logger:5001/log"
export REACT_APP_BACKEND_URL="http://remote-backend:5000"

./start_prototype.sh
```

## 🐳 Docker Deployment (Future)

Each service can be containerized:
- `ErrorLogger` - Standalone logging service
- `Backend` - AI API service
- `Frontend` - React static build served by nginx

This architecture makes the system very flexible for different deployment scenarios!
