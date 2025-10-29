import os
import requests

CORE_MEMORY_URL = os.environ.get("CORE_MEMORY_URL", "http://127.0.0.1:5010/v1")

# optional integration with core for service registration
try:
    from shared_utils.core_client import CoreClient
except Exception:
    CoreClient = None


def create_memory(text: str, agent_id: str = None, namespace: str = "global", metadata: dict = None):
    payload = {"text": text, "agent_id": agent_id, "namespace": namespace, "metadata": metadata or {}}
    r = requests.post(f"{CORE_MEMORY_URL}/memories", json=payload, timeout=5)
    r.raise_for_status()
    return r.json()


def query_memories(q: str = None, embedding: list = None, namespace: str = "global", top_k: int = 5):
    payload = {"q": q, "embedding": embedding, "namespace": namespace, "top_k": top_k}
    r = requests.post(f"{CORE_MEMORY_URL}/memories/query", json=payload, timeout=10)
    r.raise_for_status()
    return r.json()


def maybe_register_with_core():
    """Best-effort registration with RuneCore core when RUNECORE_REGISTER_WITH_CORE is set."""
    if not os.environ.get("RUNECORE_REGISTER_WITH_CORE"):
        return
    if CoreClient is None:
        print("CoreClient not available; skipping memory registration")
        return
    try:
        cc = CoreClient(core_url=os.environ.get("RUNECORE_CORE_URL"), disable_mtls=os.environ.get("RUNECORE_DISABLE_MTLS") in ("1","true","True"))
        info = {"name": "CoreMemory", "version": "0.1.0", "rest_url": os.environ.get("CORE_MEMORY_URL", CORE_MEMORY_URL)}
        res = cc.register_service(info)
        print(f"Registered memory with core: {res}")
    except Exception as e:
        print(f"Failed to register memory with core: {e}")
