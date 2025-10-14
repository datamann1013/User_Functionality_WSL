#!/usr/bin/env python3
"""
ErrorLogger Log Rotation Demo
Shows the log rotation and cleanup functionality
"""

import os
import sys
import time
import json

# Add the project to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from projects.ErrorLogger.logger import log_error, get_log_rotation_status, get_log_directory

def demo_log_rotation():
    """Demonstrate log rotation functionality"""
    print("=== ErrorLogger Log Rotation Demo ===\n")
    
    # Show initial status
    print("1. Initial Log Status:")
    status = get_log_rotation_status()
    print(f"   Log directory: {status['log_directory']}")
    print(f"   Max file size: {status['max_file_size_mb']}MB")
    print(f"   Retention: {status['retention_days']} days")
    print(f"   Current file: {status['current_file_size_mb']}MB")
    print(f"   Total log files: {status['total_log_files']}")
    print(f"   Will rotate soon: {status['will_rotate_soon']}")
    print()
    
    print("2. Creating log entries to demonstrate rotation...")
    
    # Create some log entries
    for i in range(5):
        log_error('DEMO01', 
                 message=f"Demo log entry {i+1}",
                 extra={"iteration": i+1, "demo": "rotation_test"})
        print(f"   ✓ Log entry {i+1} created")
        time.sleep(0.1)  # Small delay to show different timestamps
    
    print()
    
    # Show updated status
    print("3. Updated Log Status:")
    status = get_log_rotation_status()
    print(f"   Current file size: {status['current_file_size_mb']}MB")
    print(f"   Will rotate soon: {status['will_rotate_soon']}")
    print(f"   Total log files: {status['total_log_files']}")
    
    # Show log files in directory
    print()
    print("4. Log Files in Directory:")
    log_dir = get_log_directory()
    import glob
    log_files = glob.glob(os.path.join(log_dir, 'errorlog_*.csv'))
    log_files.sort(key=os.path.getmtime, reverse=True)  # Most recent first
    
    for i, log_file in enumerate(log_files[:3]):  # Show up to 3 most recent
        size_mb = os.path.getsize(log_file) / (1024 * 1024)
        mtime = time.ctime(os.path.getmtime(log_file))
        print(f"   {i+1}. {os.path.basename(log_file)} ({size_mb:.3f}MB, {mtime})")
        
        # Show last few lines of most recent file
        if i == 0:
            print("      Recent entries:")
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-3:]:  # Last 3 lines
                        if line.strip() and not line.startswith('timestamp;'):
                            parts = line.strip().split(';', 2)
                            if len(parts) >= 3:
                                print(f"        {parts[0]} | {parts[1]} | {parts[2]}")
            except Exception:
                pass
    
    print()
    print("5. Log Rotation Features:")
    print("   ✓ Automatic file rotation when size limit reached")
    print("   ✓ Daily cleanup of files older than retention period")
    print("   ✓ Thread-safe rotation with file locking")
    print("   ✓ Low overhead - only checks size during logging")
    print("   ✓ Configurable via config.json")
    
    print()
    print("6. Configuration Example:")
    config_example = {
        "logging": {
            "max_log_file_size_mb": 5,   # Smaller size for more frequent rotation
            "log_retention_days": 7       # Keep logs for 1 week
        }
    }
    print("   To change rotation settings, update config.json:")
    print(f"   {json.dumps(config_example, indent=4)}")
    
    print()
    print("Demo completed! Check your log directory for the created files.")
    print(f"Log directory: {log_dir}")
    print("Expected location: [project_root]/logs/errorlog_*.csv")

if __name__ == "__main__":
    demo_log_rotation()