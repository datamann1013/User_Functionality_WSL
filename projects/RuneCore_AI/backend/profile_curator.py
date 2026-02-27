"""
Profile Curator for RuneCore Mind

Runs silently in the background after each successful AI response.
Sends the last exchange to a small fast model and asks it to extract
new facts about the user. Extracted facts are appended to user_profile.

Rate-limited: at most one curation run every CURATOR_INTERVAL_SECONDS.
Uses the lightest model available (CURATOR_MODEL env var, default qwen2:0.5b).
Falls back silently if Ollama is unavailable.

Error codes: EABQ (AI Backend curation)
"""
import os
import threading
import time
import requests
from typing import Optional

CURATOR_MODEL = os.environ.get("CURATOR_MODEL", "qwen2:0.5b")
CURATOR_INTERVAL = int(os.environ.get("CURATOR_INTERVAL_SECONDS", "120"))
OLLAMA_SERVICE_URL = os.environ.get("OLLAMA_SERVICE_URL", "http://127.0.0.1:5002")

_last_run: float = 0.0
_lock = threading.Lock()


_EXTRACTION_PROMPT = """\
You are a silent fact extractor. Given a short conversation between a user and an AI, \
extract NEW factual information about the USER ONLY (not about the AI or general knowledge). \
Output ONLY a plain list of short facts, one per line, starting with a dash (-). \
If there are no new facts about the user, output nothing at all. \
Be concise — each fact should be under 15 words. \
Do not repeat facts that are already in the existing profile.\
"""


def _run_extraction(user_message: str, ai_response: str, existing_facts: list) -> list:
    """Call Ollama to extract facts. Returns list of fact strings."""
    existing_block = ""
    if existing_facts:
        existing_block = "\nAlready known facts (do NOT repeat):\n" + "\n".join(
            f"- {f}" for f in existing_facts[:30]
        )

    prompt = (
        f"{_EXTRACTION_PROMPT}\n"
        f"{existing_block}\n\n"
        f"User said: {user_message[:500]}\n"
        f"AI responded: {ai_response[:500]}\n\n"
        "New facts about the user:"
    )

    try:
        resp = requests.post(
            f"{OLLAMA_SERVICE_URL}/api/chat",
            json={
                "model": CURATOR_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.1, "num_predict": 256},
            },
            timeout=30,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        content = (data.get("message") or {}).get("content") or data.get("response", "")
        facts = []
        for line in content.splitlines():
            line = line.strip().lstrip("-").strip()
            if line and len(line) > 3 and len(line) < 200:
                facts.append(line)
        return facts
    except Exception:
        return []


def curate_async(user_message: str, ai_response: str) -> None:
    """
    Fire-and-forget: spawn a daemon thread to run fact extraction.
    Respects the rate limit — if called too soon after the last run, does nothing.
    """
    global _last_run

    now = time.monotonic()
    with _lock:
        if now - _last_run < CURATOR_INTERVAL:
            return
        _last_run = now

    def _worker():
        try:
            import user_profile
            existing = user_profile.load().get("facts", [])
            new_facts = _run_extraction(user_message, ai_response, existing)
            if new_facts:
                user_profile.add_facts(new_facts)
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
