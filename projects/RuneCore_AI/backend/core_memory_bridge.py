"""
CoreMemory Bridge for RuneCore Mind

Wraps the CoreMemory REST API (RuneCore_Memory service) with graceful
fallback — if CoreMemory is unreachable, local cache is used instead.

Two main operations:
  get_context(agent_id, message) -> list of relevant memory strings
  store_turn(agent_id, user_msg, ai_response)

Both are synchronous and must not raise — failures are swallowed and
logged to stderr so they never break chat responses.

Environment:
  CORE_MEMORY_URL  — CoreMemory base URL (default http://core_memory:5003/v1)
  CORE_MEMORY_TIMEOUT — request timeout in seconds (default 3)

Error codes: EABM (AI Backend Memory bridge)
"""
import os
import requests
from typing import List

_BASE = os.environ.get("CORE_MEMORY_URL", "http://core_memory:5003/v1")
_TIMEOUT = float(os.environ.get("CORE_MEMORY_TIMEOUT", "3"))
_TOP_K = 5  # memories to retrieve per query

# Track availability to skip retries when CoreMemory is down
_available: bool = True
_fail_count: int = 0
_MAX_FAILURES = 3


def _mark_failure() -> None:
    global _available, _fail_count
    _fail_count += 1
    if _fail_count >= _MAX_FAILURES:
        _available = False


def _mark_success() -> None:
    global _available, _fail_count
    _available = True
    _fail_count = 0


def is_available() -> bool:
    return _available


def get_context(agent_id: str, message: str) -> List[str]:
    """
    Query CoreMemory for the most relevant stored memories for this message.
    Returns a list of memory text strings (may be empty).
    Falls back silently if CoreMemory is unavailable.
    """
    if not _available:
        return []
    try:
        resp = requests.post(
            f"{_BASE}/memories/query",
            json={
                "q": message,
                "namespace": agent_id,
                "top_k": _TOP_K,
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            _mark_success()
            data = resp.json()
            memories = data.get("memories") or data.get("results") or []
            return [
                m.get("text", "") or m.get("content", "")
                for m in memories
                if isinstance(m, dict) and (m.get("text") or m.get("content"))
            ]
        _mark_failure()
        return []
    except Exception as e:
        _mark_failure()
        print(f"[WABM01] CoreMemory query failed: {e}")
        return []


def store_turn(agent_id: str, user_message: str, ai_response: str) -> bool:
    """
    Store a conversation turn in CoreMemory.
    Returns True on success, False on any failure.
    """
    if not _available:
        return False
    combined = f"User: {user_message}\nAssistant: {ai_response}"
    try:
        resp = requests.post(
            f"{_BASE}/memories",
            json={
                "text": combined,
                "agent_id": agent_id,
                "namespace": agent_id,
                "metadata": {"type": "conversation"},
            },
            timeout=_TIMEOUT,
        )
        if resp.status_code in (200, 201):
            _mark_success()
            return True
        _mark_failure()
        return False
    except Exception as e:
        _mark_failure()
        print(f"[WABM02] CoreMemory store failed: {e}")
        return False


def build_memory_block(memories: List[str]) -> str:
    """
    Format retrieved memories into a text block suitable for injection
    as additional context in the system prompt or as an initial message.
    Returns empty string if no memories.
    """
    if not memories:
        return ""
    lines = "\n".join(f"- {m}" for m in memories if m.strip())
    if not lines:
        return ""
    return f"=== Relevant Memory ===\n{lines}\n=======================\n"
