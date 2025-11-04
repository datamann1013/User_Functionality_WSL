import sys
import types
import importlib
import json
import requests


class FakeCache:
    def __init__(self):
        self._store = {}

    def get_cache_stats(self):
        return {
            "enabled": True,
            "using_redis": False,
            "message_limit": 10,
            "context_size": 5,
            "fallback_agents": len(self._store),
        }

    def format_context_for_ai(self, agent_id):
        # return empty structured history by default
        return []

    def format_chat_history_to_string(self, history):
        # Convert chat history to a simple string for Ollama
        if not history:
            return ""
        return "\n\n".join(f"{m['role']}: {m['content']}" for m in history)

    def get_full_conversation(self, agent_id):
        return list(self._store.get(agent_id, []))

    def add_conversation(self, agent_id, user_msg, ai_msg):
        entry = {
            "id": "cid-1",
            "user_message": user_msg,
            "ai_response": ai_msg,
            "timestamp": "2025-10-29T00:00:00",
        }
        self._store.setdefault(agent_id, []).insert(0, entry)

    def get_conversation_context(self, agent_id):
        return list(self._store.get(agent_id, []))


def _import_app_with_fake_cache(fake_cache):
    # Install a synthetic module used by the backend import logic
    mod = types.ModuleType("cache.conversation_cache")
    mod.conversation_cache = fake_cache
    sys.modules["cache.conversation_cache"] = mod
    # also add top-level name sometimes used in fallbacks
    sys.modules["conversation_cache"] = mod

    # Import the app module and reload to ensure our fake is picked up
    app_mod = importlib.import_module("projects.RuneCore_AI.backend.app")
    importlib.reload(app_mod)
    return app_mod


def test_health_and_agents_and_cache_stats(monkeypatch):
    fake = FakeCache()
    ai_mod = _import_app_with_fake_cache(fake)
    client = ai_mod.app.test_client()

    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert data["service"] == "ai_service"

    r = client.get("/api/agents")
    assert r.status_code == 200
    agents = r.get_json()
    assert "agents" in agents and agents["count"] >= 0

    r = client.get("/api/cache/stats")
    assert r.status_code == 200
    stats = r.get_json()
    assert stats["status"] == "ok"
    assert "cache" in stats


def test_get_agent_conversations_formatting(monkeypatch):
    fake = FakeCache()
    # populate fake cache with two messages
    fake.add_conversation("agent-1", "hello", "hi")
    fake.add_conversation("agent-1", "how are you", "good")

    ai_mod = _import_app_with_fake_cache(fake)
    client = ai_mod.app.test_client()

    r = client.get("/api/agents/agent-1/conversations")
    assert r.status_code == 200
    data = r.get_json()
    assert data["count"] == 2
    assert data["conversations"][0]["user_message"] == "how are you"


def test_log_frontend_error_posts_to_errorlogger(monkeypatch):
    fake = FakeCache()
    ai_mod = _import_app_with_fake_cache(fake)

    calls = {}

    def fake_post(url, json=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        class Dummy:
            status_code = 200

            def json(self):
                return {"ok": True}

        return Dummy()

    monkeypatch.setattr(ai_mod.requests, "post", fake_post)

    client = ai_mod.app.test_client()
    payload = {"error_code": "TEST_ERR", "message": "oops", "extra": {"foo": "bar"}}
    r = client.post("/api/log-frontend-error", json=payload)
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "logged"
    assert calls["url"] == ai_mod.ERRORLOGGER_URL


def test_chat_missing_message_returns_400(monkeypatch):
    fake = FakeCache()
    ai_mod = _import_app_with_fake_cache(fake)
    client = ai_mod.app.test_client()

    r = client.post("/api/chat", json={})
    assert r.status_code == 400


def test_chat_ollama_success_and_timeout_and_graceful(monkeypatch):
    fake = FakeCache()
    ai_mod = _import_app_with_fake_cache(fake)
    client = ai_mod.app.test_client()

    # 1) Successful Ollama response
    def good_post(url, json=None, timeout=None):
        class DummyResp:
            status_code = 200

            def json(self):
                return {"response": "OK from Ollama"}

        return DummyResp()

    monkeypatch.setattr(ai_mod.requests, "post", good_post)

    r = client.post("/api/chat", json={"message": "hey there", "agent_id": "agent-1"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["response"] == "OK from Ollama"
    assert d["mode"] == "ollama"

    # 2) Timeout
    def timeout_post(url, json=None, timeout=None):
        raise ai_mod.requests.exceptions.Timeout()

    monkeypatch.setattr(ai_mod.requests, "post", timeout_post)

    r = client.post("/api/chat", json={"message": "this will timeout", "agent_id": "agent-1"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["mode"] == "timeout_fallback"

    # 3) Graceful fallback for keywords
    def err_post(url, json=None, timeout=None):
        raise Exception("conn error")

    monkeypatch.setattr(ai_mod.requests, "post", err_post)

    r = client.post("/api/chat", json={"message": "hello, AI", "agent_id": "agent-1"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["mode"] == "graceful_fallback"
    assert "Hello" in d["response"] or "hello" in d["response"].lower()
