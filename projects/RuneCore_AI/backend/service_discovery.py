"""
Service Discovery and Integrated Mode Support for RuneCore AI

This module handles:
- Detection of standalone vs integrated mode
- Service discovery through Core
- Limb mode with local SQLite persistence
- Dependency notification handling
- Automatic sync when dependencies become available
"""
import os
import time
import json
import sqlite3
import threading
import requests
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# Global state
LIMB_MODE = False
STANDALONE_MODE = False
INTEGRATION_MODE = False
SERVICE_URLS = {}
URL_CACHE = {}
URL_CACHE_TTL = 60  # seconds
LOCAL_DB_PATH = "/tmp/limb_conversations.db"


class LimbModeStorage:
    """Local SQLite storage for limb mode conversations"""
    
    def __init__(self, db_path: str = LOCAL_DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS limb_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    message_history TEXT NOT NULL,
                    timestamp INTEGER NOT NULL
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_agent_timestamp ON limb_conversations(agent_id, timestamp DESC)')
            conn.commit()
            conn.close()
            print(f"[IAFX02] Limb mode storage initialized at {self.db_path}")
        except Exception as e:
            print(f"[EAFX02] Failed to initialize limb mode storage: {e}")
    
    def store_conversation(self, agent_id: str, user_message: str, ai_response: str):
        """Store single conversation turn in local database with LRU eviction"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Store new conversation
            timestamp = int(time.time())
            conversation = {
                "agent_id": agent_id,
                "user_message": user_message,
                "ai_response": ai_response,
                "timestamp": datetime.fromtimestamp(timestamp).isoformat()
            }
            history_json = json.dumps(conversation)
            cursor.execute(
                'INSERT INTO limb_conversations (agent_id, message_history, timestamp) VALUES (?, ?, ?)',
                (agent_id, history_json, timestamp)
            )
            
            # Keep only last 10 conversations per agent (LRU eviction)
            cursor.execute('''
                DELETE FROM limb_conversations 
                WHERE agent_id = ? AND id NOT IN (
                    SELECT id FROM limb_conversations 
                    WHERE agent_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 10
                )
            ''', (agent_id, agent_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[EAFX03] Failed to store limb conversation: {e}")
            return False
    
    def get_last_n_conversations(self, agent_id: str, n: int = 10) -> List[Dict]:
        """Retrieve last N conversations for an agent"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT message_history FROM limb_conversations 
                WHERE agent_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (agent_id, n))
            rows = cursor.fetchall()
            conn.close()
            
            conversations = []
            for row in rows:
                try:
                    history = json.loads(row[0])
                    conversations.append(history)
                except Exception:
                    continue
            return conversations
        except Exception as e:
            print(f"[EAFX04] Failed to retrieve limb conversations: {e}")
            return []
    
    def get_all_agent_ids(self) -> List[str]:
        """Get list of all agent IDs with stored conversations"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT agent_id FROM limb_conversations')
            rows = cursor.fetchall()
            conn.close()
            return [row[0] for row in rows]
        except Exception as e:
            print(f"[EAFX06] Failed to get agent IDs: {e}")
            return []
            conn.close()
            
            conversations = []
            for row in rows:
                try:
                    history = json.loads(row[0])
                    conversations.append(history)
                except Exception:
                    continue
            return conversations
        except Exception as e:
            print(f"[EAFX04] Failed to retrieve limb conversations: {e}")
            return []
    
    def get_record_count(self, agent_id: Optional[str] = None) -> int:
        """Get count of stored records"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if agent_id:
                cursor.execute('SELECT COUNT(*) FROM limb_conversations WHERE agent_id = ?', (agent_id,))
            else:
                cursor.execute('SELECT COUNT(*) FROM limb_conversations')
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0
    
    def clear_agent_data(self, agent_id: str):
        """Clear all data for an agent (after successful sync)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM limb_conversations WHERE agent_id = ?', (agent_id,))
            conn.commit()
            conn.close()
            print(f"[IAFX03] Cleared limb mode data for agent {agent_id}")
        except Exception as e:
            print(f"[EAFX05] Failed to clear limb data: {e}")
    
    def clear_all(self):
        """Clear all limb mode data (after successful sync)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM limb_conversations')
            conn.commit()
            conn.close()
            print("[IAFX07] Cleared all limb mode data")
        except Exception as e:
            print(f"[EAFX08] Failed to clear all limb data: {e}")


# Global limb storage instance
limb_storage = None


def get_limb_storage() -> Optional[LimbModeStorage]:
    """Get global limb storage instance"""
    return limb_storage


def detect_mode() -> Tuple[bool, bool, bool]:
    """
    Detect operation mode: standalone, integrated, or limb
    
    Returns:
        (standalone, integrated, limb): Mode flags
    """
    global STANDALONE_MODE, INTEGRATION_MODE, LIMB_MODE, limb_storage
    
    core_url = os.environ.get("RUNECORE_CORE_URL", "")
    
    if not core_url:
        # No Core URL configured - standalone mode
        STANDALONE_MODE = True
        INTEGRATION_MODE = False
        LIMB_MODE = False
        print("[IAFX04] Running in STANDALONE mode (no Core configured)")
        return True, False, False
    
    # Try to register with Core
    try:
        registration_result = register_with_core()
        
        if registration_result["registered"]:
            status = registration_result.get("status", "running")
            missing_deps = registration_result.get("missing_dependencies", [])
            
            if status == "limb_mode" or missing_deps:
                # Registered but missing dependencies - limb mode
                STANDALONE_MODE = False
                INTEGRATION_MODE = True
                LIMB_MODE = True
                
                # Initialize limb storage
                limb_storage = LimbModeStorage()
                
                print(f"[WAFX01] Running in LIMB MODE - missing dependencies: {missing_deps}")
                return False, True, True
            else:
                # Fully integrated
                STANDALONE_MODE = False
                INTEGRATION_MODE = True
                LIMB_MODE = False
                print("[IAFX05] Running in INTEGRATED mode")
                return False, True, False
        else:
            # Registration failed - standalone fallback
            STANDALONE_MODE = True
            INTEGRATION_MODE = False
            LIMB_MODE = False
            print("[WAFX02] Failed to register with Core, running in STANDALONE mode")
            return True, False, False
            
    except Exception as e:
        print(f"[EAFX06] Error detecting mode: {e}")
        STANDALONE_MODE = True
        INTEGRATION_MODE = False
        LIMB_MODE = False
        return True, False, False


def register_with_core() -> Dict:
    """
    Register service with Core
    
    Returns:
        Registration response with status and dependencies
    """
    core_url = os.environ.get("RUNECORE_CORE_URL", "")
    if not core_url:
        return {"registered": False, "error": "No Core URL configured"}
    
    cert_path = os.environ.get("CLIENT_CERT_PATH", "")
    key_path = os.environ.get("CLIENT_KEY_PATH", "")
    ca_path = os.environ.get("CA_CERT_PATH", "")
    container_name = os.environ.get("CONTAINER_NAME", "")
    
    # Build registration payload
    rest_url = os.environ.get("AI_SERVICE_URL", "http://localhost:5000")
    payload = {
        "name": "AIBackend",
        "version": "0.1.0",
        "rest_url": rest_url,
        "dependencies": ["CoreMemoryAPI", "RuneGuardLogger"],
        "wishlist": [],
        "container_name": container_name
    }
    
    # Prepare request kwargs
    kwargs = {"json": payload, "timeout": 10}
    
    # Add mTLS if certificates available
    if cert_path and key_path and os.path.exists(cert_path) and os.path.exists(key_path):
        kwargs["cert"] = (cert_path, key_path)
        if ca_path and os.path.exists(ca_path):
            kwargs["verify"] = ca_path
        else:
            kwargs["verify"] = False
        print(f"[IAFX06] Registering with mTLS using cert: {cert_path}")
    else:
        kwargs["verify"] = False
        print("[WAFX03] Registering without mTLS (certificates not found)")
    
    # Attempt registration with retries
    for attempt in range(5):
        try:
            response = requests.post(f"{core_url}/api/v1/services/register", **kwargs)
            
            if response.status_code == 200:
                data = response.json()
                print(f"[IAFX07] Registration successful: {data}")
                return data
            else:
                print(f"[WAFX04] Registration attempt {attempt + 1} failed: {response.status_code}")
                
        except Exception as e:
            print(f"[WAFX05] Registration attempt {attempt + 1} error: {e}")
        
        if attempt < 4:
            # Exponential backoff
            wait_time = 2 ** attempt
            time.sleep(wait_time)
    
    return {"registered": False, "error": "Failed after retries"}


def get_service_url(service_name: str, required: bool = False) -> Optional[str]:
    """
    Get service URL from Core registry with caching
    
    Args:
        service_name: Name of the service
        required: If True, raise exception if service not found
        
    Returns:
        Service URL or None
    """
    global URL_CACHE, INTEGRATION_MODE, LIMB_MODE
    
    # Return None in standalone mode
    if STANDALONE_MODE:
        return None
    
    # Return None for optional services in limb mode
    if LIMB_MODE and not required:
        return None
    
    # Check cache
    cache_key = service_name
    if cache_key in URL_CACHE:
        cached_url, timestamp = URL_CACHE[cache_key]
        if time.time() - timestamp < URL_CACHE_TTL:
            return cached_url
    
    # Query Core
    core_url = os.environ.get("RUNECORE_CORE_URL", "")
    if not core_url:
        if required:
            raise Exception(f"Service {service_name} required but Core not configured")
        return None
    
    try:
        cert_path = os.environ.get("CLIENT_CERT_PATH", "")
        key_path = os.environ.get("CLIENT_KEY_PATH", "")
        ca_path = os.environ.get("CA_CERT_PATH", "")
        
        kwargs = {"timeout": 5}
        if cert_path and key_path and os.path.exists(cert_path):
            kwargs["cert"] = (cert_path, key_path)
            kwargs["verify"] = ca_path if ca_path and os.path.exists(ca_path) else False
        else:
            kwargs["verify"] = False
        
        response = requests.get(
            f"{core_url}/api/v1/services/query",
            params={"name": service_name},
            **kwargs
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("available"):
                service_url = data.get("rest_url")
                # Cache the URL
                URL_CACHE[cache_key] = (service_url, time.time())
                return service_url
        
        if required:
            raise Exception(f"Service {service_name} not available")
        return None
        
    except Exception as e:
        print(f"[EAFX07] Failed to query service {service_name}: {e}")
        if required:
            raise
        return None


def heartbeat_loop():
    """Background thread that sends heartbeats to Core"""
    global INTEGRATION_MODE, LIMB_MODE
    
    while True:
        try:
            if INTEGRATION_MODE:
                core_url = os.environ.get("RUNECORE_CORE_URL", "")
                if core_url:
                    status = "limb_mode" if LIMB_MODE else "healthy"
                    
                    # Get local record count for metadata
                    local_records = 0
                    if limb_storage:
                        local_records = limb_storage.get_record_count()
                    
                    payload = {
                        "name": "AIBackend",
                        "status": status,
                        "metadata": {
                            "local_records_count": local_records,
                            "limb_mode": LIMB_MODE
                        }
                    }
                    
                    cert_path = os.environ.get("CLIENT_CERT_PATH", "")
                    key_path = os.environ.get("CLIENT_KEY_PATH", "")
                    ca_path = os.environ.get("CA_CERT_PATH", "")
                    
                    kwargs = {"json": payload, "timeout": 5}
                    if cert_path and key_path and os.path.exists(cert_path):
                        kwargs["cert"] = (cert_path, key_path)
                        kwargs["verify"] = ca_path if ca_path and os.path.exists(ca_path) else False
                    else:
                        kwargs["verify"] = False
                    
                    response = requests.post(f"{core_url}/api/v1/services/heartbeat", **kwargs)
                    if response.status_code != 200:
                        print(f"[WAFX06] Heartbeat failed: {response.status_code}")
                        
        except Exception as e:
            print(f"[EAFX08] Heartbeat error: {e}")
        
        # Send heartbeat every 30 seconds
        time.sleep(30)


def start_heartbeat_thread():
    """Start background heartbeat thread"""
    if INTEGRATION_MODE:
        thread = threading.Thread(target=heartbeat_loop, daemon=True, name="HeartbeatThread")
        thread.start()
        print("[IAFX08] Heartbeat thread started")


# Initialize mode detection on module import
# This will be called when app.py imports this module
