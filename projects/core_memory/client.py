import os
import requests

CORE_MEMORY_URL = os.environ.get("CORE_MEMORY_URL", "http://127.0.0.1:5010/v1")


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
