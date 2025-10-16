# ErrorLogger v1.1

> **Status**: ✅ Production Ready | **Integration**: AI Service Platform  
> **Last Updated**: October 16, 2025

Centralized error logging system for WSL-based development environments with structured error codes, web interface, and cross-project integration.

## Features

### Core Functionality
- **Structured Error Codes**: `[Type][Origin][Component][Subcomponent][Number]`
  - Type: E=Error, W=Warning, I=Info
  - Origin: A=AI Service, F=Frontend, B=Backend
  - Component: S=Setup, B=Backend, F=Frontend
  - Subcomponent: Specific module (A=API, M=Model, etc)
- **CSV Log Format**: Semicolon-delimited for easy database import
- **Standard Messages**: Automatic fallback with "(standard)" tag
- **WSL Optimized**: Special path handling for WSL environments
- **Sync Logging**: Guaranteed log delivery with response validation

### Project Integration Status
- ✅ **AI Service Backend**: Fully integrated with service identification
- ✅ **Ollama Service**: Complete error tracking and monitoring
- ⚠️ **AI Service Frontend**: Partial integration (pending Phase 1 completion)
- ✅ **Startup Scripts**: Enhanced ErrorLogger detection and management
- ✅ **Cross-Service**: Centralized logging across all components

### Web Interface
- **Real-time Monitoring**: Live error tracking dashboard
- **Error Analysis**: Pattern detection and trending
- **Service Health**: Component status monitoring
- **Log Export**: CSV and JSON export capabilities

## Log Format
```csv
timestamp;error_code;explanation;exception;extra
```

Example:
```
2023-08-04 15:30:22;EABS1;Missing required model files;FileNotFoundError;{"missing_files": ["model.bin"]}
```

## Error Code Structure
| Segment       | Values      | Description                     |
|---------------|-------------|---------------------------------|
| Type (1 char) | E, W, I     | Error, Warning, Info           |
| Origin (1)    | A, F, B     | AI Service, Frontend, Backend  |
| Component (1) | S, B, F, X  | Setup, Backend, Frontend, General |
| Subcomponent  | A-Z, #      | Specific module or # for general |
| Number (2)    | 00-99       | Unique error ID                |

Example: `EABS1` = Error + AI Service + Backend + Setup + ID 01

## Installation
```bash
pip install -e ./projects/ErrorLogger
```

## Configuration
The logger uses `config.json` for settings. Example configuration:
```json
{
  "error_explanations": {
    "EABS1": "Missing required model files",
    "EABB1": "Inference failed - model loading issue"
  },
  "logging": {
    "enable_console_debug": false,
    "log_retention_days": 30,
    "max_log_file_size_mb": 10
  },
  "service": {
    "remote_url": "http://localhost:5001/log",
    "timeout_seconds": 5,
    "retry_attempts": 1
  }
}
```

**Log Rotation**: Automatic size-based rotation with time-based cleanup
- Files rotate when they reach `max_log_file_size_mb` (default: 10MB)
- Old files auto-delete after `log_retention_days` (default: 30 days)
- Cleanup runs once daily (low overhead)

**Fallback**: If `config.json` is missing or incomplete, the system automatically falls back to `error_codes.py` definitions.

**Debug Mode**: Set `enable_console_debug: true` in config or use `DEBUG=1` environment variable for console output.

## Usage

### AI Service Integration (Recommended)
```python
# AI Service backend integration (auto-service identification)
sys.path.append('/home/administrator/gitcontrol/User_Functionality_WSL/projects')
from ErrorLogger.logger import log_error_remote

def log_to_errorlogger(error_code, message=None, exception=None, extra=None):
    """Log to ErrorLogger with proper service identification"""
    if extra is None:
        extra = {}
    extra['service'] = 'ai_service'  # Auto-identifies service
    return log_error_remote(error_code, message, exception, extra)

# Usage in AI service
try:
    agent = db.create_agent(agent_data)
except Exception as e:
    log_to_errorlogger('EABD02', 'Failed to create agent', exception=e)
```

### Direct Python Logging
```python
from ErrorLogger.logger import log_error_remote

try:
    # Your code here
except Exception as e:
    log_error_remote(
        "EABB1",
        message="Inference failed",
        exception=str(e),
        extra={"model": "llama3.2:1b", "service": "ollama_service"}
    )
```

### React Logging (Frontend)
```javascript
// errorLogger.js
export function logReactError(code, message, error, extra) {
  fetch('http://localhost:5001/log', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      error_code: code,
      message: message,
      exception: error.toString(),
      extra: extra
    })
  });
}

// Usage
try {
  // Component logic
} catch (error) {
  logReactError('EAFX1', 'UI render failed', error, {component: 'ChatWindow'});
}
```

### Starting Service
```bash
error-logger  # Starts on port 5001
```

## Testing
```bash
pytest projects/ErrorLogger/test_logger.py
```

## Viewing Logs
Logs are stored in the `logs/` directory within the project:
```bash
# View all logs
tail -f logs/errorlog_*.csv

# View latest log file only
tail -f $(ls -t logs/errorlog_*.csv | head -1)

# View logs from project root
cd /path/to/User_Functionality_WSL
tail -f logs/errorlog_*.csv
```

## Log Rotation Monitoring
```python
from ErrorLogger.logger import get_log_rotation_status

status = get_log_rotation_status()
print(f"Current file: {status['current_file_size_mb']}MB")
print(f"Will rotate: {status['will_rotate_soon']}")
print(f"Total files: {status['total_log_files']}")
```

## Adding New Error Codes
1. Edit `error_codes.py`
2. Add new codes with explanations
3. Follow naming convention