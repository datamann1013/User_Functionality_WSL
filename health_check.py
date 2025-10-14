#!/usr/bin/env python3
"""
Quick health check script for AI Service Platform
Tests connectivity to all services
"""

import requests
import sys
import time

def check_service(name, url, timeout=5):
    """Check if a service is responding"""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            print(f"✅ {name}: OK")
            return True
        else:
            print(f"⚠️  {name}: Responding but status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ {name}: Connection refused")
        return False
    except requests.exceptions.Timeout:
        print(f"⏰ {name}: Timeout")
        return False
    except Exception as e:
        print(f"❌ {name}: Error - {e}")
        return False

def main():
    print("🔍 AI Service Platform Health Check")
    print("===================================")
    
    services = [
        ("ErrorLogger", "http://localhost:5001/health"),
        ("Backend API", "http://localhost:5000/health"),
        ("Frontend", "http://localhost:3000")
    ]
    
    all_healthy = True
    
    for name, url in services:
        if not check_service(name, url):
            all_healthy = False
    
    print()
    if all_healthy:
        print("🎉 All services are healthy!")
        return 0
    else:
        print("⚠️  Some services are not responding")
        print("💡 Try running ./start_ai_service.sh to start services")
        return 1

if __name__ == "__main__":
    sys.exit(main())
