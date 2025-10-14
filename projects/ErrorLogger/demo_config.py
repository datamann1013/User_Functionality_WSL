#!/usr/bin/env python3
"""
ErrorLogger Configuration Demo
Shows the enhanced ErrorLogger with config.json integration
"""

import os
import sys
import json
from datetime import datetime

# Add the project to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from projects.ErrorLogger.logger import log_error, log_error_remote, CONFIG

def demo_configuration():
    """Demonstrate the configuration system"""
    print("=== ErrorLogger Configuration Demo ===\n")
    
    print("1. Configuration Overview:")
    print(f"   - Error explanations loaded: {len(CONFIG['error_explanations'])}")
    print(f"   - Remote service URL: {CONFIG['service']['remote_url']}")
    print(f"   - Timeout: {CONFIG['service']['timeout_seconds']}s")
    print(f"   - Debug mode: {CONFIG['logging']['enable_console_debug']}")
    print()
    
    print("2. Testing different error codes:")
    
    # Test known error codes
    test_codes = ['EABS1', 'EABB1', 'IAFX1', 'UNKNOWN_CODE']
    
    for code in test_codes:
        print(f"   {code}: ", end="")
        
        # Test with just error code (uses config explanation)
        log_error(code)
        print("✓ Logged")
    
    print()
    print("3. Testing with custom messages:")
    
    # Test with custom message
    log_error('EABS1', message="Custom message overrides config")
    print("   ✓ Custom message logged")
    
    # Test with exception and extra data
    try:
        raise ValueError("Demo exception")
    except Exception as e:
        log_error('EABB1', exception=str(e), extra={"demo": "data"})
        print("   ✓ Exception with extra data logged")
    
    print()
    print("4. Configuration features:")
    
    # Show config file location
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    print(f"   Config file: {config_path}")
    print(f"   Config exists: {os.path.exists(config_path)}")
    
    # Show fallback behavior
    print("   ✓ Automatic fallback to error_codes.py when config incomplete")
    print("   ✓ Environment variable support (DEBUG=1)")
    print("   ✓ WSL-optimized log paths")
    
    print()
    print("5. Debug mode demonstration:")
    print("   Set DEBUG=1 environment variable or enable_console_debug in config")
    print("   to see real-time console output")
    
    print()
    print(f"Demo completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Check ~/logs/ for log files (WSL) or project root (other systems)")

if __name__ == "__main__":
    demo_configuration()