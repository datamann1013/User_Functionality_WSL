"""
Service Discovery for CoreMemory API

Handles:
- Registration with RuneCore_Core
- Heartbeat monitoring
- Service URL lookup (for other services)
"""
import os
import time
import threading
import requests
from typing import Optional, Dict
import socket

# Global state
REGISTERED = False
CORE_URL = os.environ.get("RUNECORE_CORE_URL", "")
SERVICE_NAME = "CoreMemoryAPI"
SERVICE_PORT = int(os.environ.get("PORT", "8000"))
# Configurable URLs: REST URL must include /v1 so Core proxy routes correctly;
# heartbeat URL points to HA node to offload health processing from Core.
_REST_URL_OVERRIDE = os.environ.get("RUNECORE_REST_URL", "")
HEARTBEAT_URL = os.environ.get(
    "RUNECORE_HEARTBEAT_URL",
    f"{CORE_URL}/api/v1/services/heartbeat" if CORE_URL else ""
)

# Certificate paths for mTLS
CERT_PATH = os.environ.get("CERT_PATH", "/certs/core_memory_api.pem")
KEY_PATH = os.environ.get("KEY_PATH", "/certs/core_memory_api.key")
CA_CERT_PATH = os.environ.get("CA_CERT_PATH", "/certs/ca_cert.pem")

# Heartbeat thread
_heartbeat_thread = None
_heartbeat_running = False


def get_container_name() -> str:
    """Get Docker container name from hostname"""
    try:
        return socket.gethostname()
    except Exception:
        return "unknown"


def get_mtls_config() -> Optional[tuple]:
    """Get mTLS certificate configuration if available"""
    try:
        if os.path.exists(CERT_PATH) and os.path.exists(KEY_PATH):
            if os.path.exists(CA_CERT_PATH):
                return (CERT_PATH, KEY_PATH), CA_CERT_PATH
            else:
                return (CERT_PATH, KEY_PATH), None
    except Exception:
        pass
    return None


def register_with_core() -> Dict:
    """
    Register CoreMemoryAPI with RuneCore_Core
    
    Returns:
        Registration response with status and missing dependencies
    """
    global REGISTERED
    
    if not CORE_URL:
        print("[WARN] RUNECORE_CORE_URL not set, running standalone")
        return {"registered": False, "reason": "no_core_url"}
    
    # Build registration payload
    container_name = get_container_name()
    rest_url = _REST_URL_OVERRIDE or f"http://{container_name}:{SERVICE_PORT}"
    
    payload = {
        "name": SERVICE_NAME,
        "version": "0.2.0",
        "rest_url": rest_url,
        "dependencies": [],  # No dependencies - we provide database access
        "wishlist": ["RuneGuardLogger"],  # Optional error logging
        "container_name": container_name
    }
    
    # Attempt registration with retries
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[INFO] Registering with Core (attempt {attempt}/{max_retries})...")
            
            # Get mTLS config
            mtls_config = get_mtls_config()
            
            if mtls_config:
                cert, verify = mtls_config
                response = requests.post(
                    f"{CORE_URL}/api/v1/services/register",
                    json=payload,
                    cert=cert,
                    verify=verify if verify else False,
                    timeout=10
                )
            else:
                print("[WARN] mTLS certificates not found, using HTTP")
                response = requests.post(
                    f"{CORE_URL}/api/v1/services/register",
                    json=payload,
                    timeout=10
                )
            
            if response.status_code == 200:
                result = response.json()
                REGISTERED = result.get("registered", False)
                
                if REGISTERED:
                    status = result.get("status", "running")
                    print(f"[INFO] Registered with Core - status: {status}")
                    return result
                else:
                    print(f"[WARN] Registration rejected: {result}")
                    return result
            else:
                print(f"[WARN] Registration failed: {response.status_code} {response.text}")
                
        except Exception as e:
            print(f"[ERROR] Registration attempt {attempt} failed: {e}")
            
            if attempt < max_retries:
                delay = 2 ** attempt  # Exponential backoff
                print(f"[INFO] Retrying in {delay}s...")
                time.sleep(delay)
    
    print("[ERROR] Failed to register with Core after all retries")
    return {"registered": False, "reason": "max_retries_exceeded"}


def send_heartbeat():
    """Send heartbeat to Core"""
    if not REGISTERED or not CORE_URL:
        return
    
    try:
        # Get database status
        from .db import SessionLocal, engine
        from sqlalchemy import text
        db_status = "healthy"
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            db_status = "database_unreachable"
        
        payload = {
            "name": SERVICE_NAME,
            "status": db_status,
            "metadata": {
                "postgres_connected": db_status == "healthy",
                "service_type": "database_api"
            }
        }
        
        mtls_config = get_mtls_config()
        
        if mtls_config:
            cert, verify = mtls_config
            response = requests.post(
                HEARTBEAT_URL,
                json=payload,
                cert=cert,
                verify=verify if verify else False,
                timeout=5
            )
        else:
            response = requests.post(
                HEARTBEAT_URL,
                json=payload,
                timeout=5
            )
        
        if response.status_code != 200:
            print(f"[WARN] Heartbeat failed: {response.status_code}")
            
    except Exception as e:
        print(f"[ERROR] Heartbeat exception: {e}")


def heartbeat_loop():
    """Background thread for sending heartbeats"""
    global _heartbeat_running
    
    while _heartbeat_running:
        send_heartbeat()
        time.sleep(30)  # 30-second interval


def start_heartbeat_thread():
    """Start the heartbeat background thread"""
    global _heartbeat_thread, _heartbeat_running
    
    if _heartbeat_thread and _heartbeat_thread.is_alive():
        print("[WARN] Heartbeat thread already running")
        return
    
    _heartbeat_running = True
    _heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    _heartbeat_thread.start()
    print("[INFO] Heartbeat thread started")


def stop_heartbeat_thread():
    """Stop the heartbeat background thread"""
    global _heartbeat_running
    
    _heartbeat_running = False
    if _heartbeat_thread:
        _heartbeat_thread.join(timeout=5)
    print("[INFO] Heartbeat thread stopped")


def get_service_url(service_name: str) -> Optional[str]:
    """
    Lookup service URL from Core registry
    
    Args:
        service_name: Name of service to lookup
        
    Returns:
        Service URL or None if not found
    """
    if not CORE_URL:
        return None
    
    try:
        mtls_config = get_mtls_config()
        
        params = {"name": service_name}
        
        if mtls_config:
            cert, verify = mtls_config
            response = requests.get(
                f"{CORE_URL}/api/v1/services/query",
                params=params,
                cert=cert,
                verify=verify if verify else False,
                timeout=5
            )
        else:
            response = requests.get(
                f"{CORE_URL}/api/v1/services/query",
                params=params,
                timeout=5
            )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("found"):
                return result.get("rest_url") or result.get("ws_url")
        
    except Exception as e:
        print(f"[ERROR] Service lookup failed for {service_name}: {e}")
    
    return None
