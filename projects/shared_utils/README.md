# Shared Utils

> **Status**: ✅ Supporting Library | **Integration**: Cross-Project  
> **Last Updated**: October 16, 2025

Common utilities and constants shared across all projects in the User Functionality WSL repository.

## Purpose

This module provides:
- **Shared Constants**: Common configuration values used across projects
- **Cross-Project Compatibility**: Ensures consistent behavior between components
- **Centralized Configuration**: Single source of truth for shared settings

## Contents

### `constants.py`
Contains shared constants and configuration values used across multiple projects:
- Service URLs and port configurations
- Common file paths and directory structures
- Error code prefixes and categories
- Default timeout and retry values

## Usage

```python
# Import shared constants in any project
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'shared_utils'))
from constants import DEFAULT_TIMEOUT, SERVICE_PORTS

# Use in your code
timeout = DEFAULT_TIMEOUT
port = SERVICE_PORTS['errorlogger']
```

## Integration Status

| Project | Integration | Usage |
|---------|-------------|-------|
| **AI Service** | ✅ Active | Service configurations, error prefixes |
| **ErrorLogger** | ✅ Active | Error code structures, service identification |
| **Hidden Toolbar** | ⚠️ Minimal | Future integration planned |

## Future Enhancements

- **Configuration Management**: Centralized config file handling
- **Path Utilities**: Cross-platform path resolution helpers
- **Service Discovery**: Common service location and health check utilities
- **Logging Helpers**: Shared logging configuration and formatters
