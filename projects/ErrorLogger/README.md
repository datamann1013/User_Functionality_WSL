# ErrorLogger v1.1

Error logging system for WSL-based development environments with structured error codes and CSV logging.

## Features
- **Structured Error Codes**: `[Type][Origin][Component][Subcomponent][Number]`
  - Type: E=Error, W=Warning, I=Info
  - Origin: A=AI Service, F=Frontend, B=Backend
  - Component: S=Setup, B=Backend, F=Frontend
  - Subcomponent: Specific module (A=API, M=Model, etc)
- **CSV Log Format**: Semicolon-delimited for easy database import
- **Standard Messages**: Automatic fallback with "(standard)" tag
- **WSL Optimized**: Special path handling for WSL environments
- **Sync Logging**: Guaranteed log delivery with response validation

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

## Usage
### Python Logging
```python
from ErrorLogger.logger import log_error_remote

try:
    # Your code here
except Exception as e:
    log_error_remote(
        "EABB1",
        message="Inference failed",
        exception=str(e),
        extra={"model": "opt-6.7b"}
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
Logs are stored in `~/logs/` (WSL) or project root (other systems):
```bash
# WSL
tail -f ~/logs/errorlog_*.csv

# Other
tail -f errorlog_*.csv
```

## Adding New Error Codes
1. Edit `error_codes.py`
2. Add new codes with explanations
3. Follow naming convention