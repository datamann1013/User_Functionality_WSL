# ErrorLogger

A robust, configurable error logging utility for Python projects. It provides structured error codes, log file rotation, and automatic interception of uncaught exceptions.

## Features
- **Structured error codes**: Codes like `EABA12` (level, origin, component, subcomponent, number)
- **Log levels**: Error, Warning, Info, etc. (first letter of code)
- **Component tracking**: Origin, component, subcomponent, and error number
- **Automatic log file rotation**: New log file with timestamp (to milliseconds) on each boot
- **Configurable explanations**: Explanations for error codes from a JSON config file
- **Python exception logging**: All uncaught exceptions are logged with code `00000`
- **Thread-safe logging**: Uses a lock to prevent race conditions
- **Tested**: Comprehensive pytest suite

## Usage

### Logging an error
```python
from projects.ErrorLogger import logger
logger.log_error('EABA12', message='Something went wrong')
```

### Logging a warning or info
```python
logger.log_error('WABA12', message='This is a warning')
logger.log_error('IABA12', message='Just info')
```

### Logging a Python exception
```python
try:
    1 / 0
except Exception as e:
    logger.log_error(0, exception=e)  # Will log with code 00000
```

### Automatic interception of uncaught exceptions
Any uncaught exception will be logged automatically with code `00000` and full traceback.

### Error code generation
```python
code = logger.generate_error_code('E', 'A', 'B', 'A', 12)  # 'EABA12'
code = logger.generate_error_code('W', 'A', 'F', '', 12)   # 'WAF#12'
```

### Explanations from config
Add explanations for error codes in `config.json`:
```json
{
  "EABA12": "AI service backend API error"
}
```

## Log file location
A new log file is created in the project root on each boot, named like `errorlog_YYYYMMDD_HHMMSS_mmm.log`.

## Testing
Run all tests with:
```
pytest projects/ErrorLogger/test_logger.py
```

## Extending
- Add new error code components in `constants.py`.
- Add new explanations in `config.json`.

---
For more details, see the code and tests in this module.

