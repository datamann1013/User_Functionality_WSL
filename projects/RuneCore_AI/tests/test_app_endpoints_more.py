import importlib
import sys
import types
import pytest


def setup_ai(monkeypatch):
    # Import module fresh
    if "projects.RuneCore_AI.backend.app" in sys.modules:
        del sys.modules["projects.RuneCore_AI.backend.app"]
    ai_mod = importlib.import_module("projects.RuneCore_AI.backend.app")
    importlib.reload(ai_mod)

    # Replace conversation_cache with a simple stub
    class StubCache:
        def __init__(self):
            self._calls = []

        def get_cache_stats(self):
            return {"using_redis": False, "message_limit": 10, "context_size": 3}

        def get_full_conversation(self, agent_id):
            return [
                {"id": "1", "user_message": "hi", "ai_response": "hello", "timestamp": "t1"},
                {"id": "2", "user_message": "how", "ai_response": "now", "timestamp": "t2"},
            ]

        def format_context_for_ai(self, agent_id):
            return []

        def format_chat_history_to_string(self, history):
            return "".join([h.get("content", "") for h in history])

        def add_conversation(self, agent_id, user_msg, ai_msg):
            self._calls.append((agent_id, user_msg, ai_msg))

        def get_conversation_context(self, agent_id):
            return ["m1", "m2"]

    stub = StubCache()
    ai_mod.conversation_cache = stub
    return ai_mod, ai_mod.app


def test_get_agents_endpoint():
    ai_mod, app = setup_ai(None)
    client = app.test_client()
    r = client.get("/api/agents")
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("count") == 2


def test_get_cache_stats_ok():
    ai_mod, app = setup_ai(None)
    client = app.test_client()
    r = client.get("/api/cache/stats")
    assert r.status_code == 200
    j = r.get_json()
    assert j["status"] == "ok"
    assert "cache" in j


def test_get_cache_stats_error(monkeypatch):
    ai_mod, app = setup_ai(None)

    class BadCache:
        def get_cache_stats(self):
            raise RuntimeError("boom")

    ai_mod.conversation_cache = BadCache()
    client = app.test_client()
    r = client.get("/api/cache/stats")
    assert r.status_code == 500


def test_get_agent_conversations_ok():
    ai_mod, app = setup_ai(None)
    client = app.test_client()
    r = client.get("/api/agents/some-agent/conversations")
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("source") == "local_cache"
    assert j.get("count") == 2


def test_get_agent_conversations_error(monkeypatch):
    ai_mod, app = setup_ai(None)

    class BadCache:
        def get_full_conversation(self, agent_id):
            raise RuntimeError("cache fail")

    ai_mod.conversation_cache = BadCache()
    client = app.test_client()
    r = client.get("/api/agents/agent-1/conversations")
    assert r.status_code == 500


def test_log_frontend_error_and_requests_failure(monkeypatch):
    ai_mod, app = setup_ai(None)
    client = app.test_client()

    # Normal path
    r = client.post("/api/log-frontend-error", json={"error_code": "E1", "message": "oops"})
    assert r.status_code == 200

    # Simulate requests.post raising RequestException
    class DummyRequests:
        class RequestException(Exception):
            pass

        class Timeout(Exception):
            pass

        def post(self, *a, **k):
            raise DummyRequests.RequestException()

    ai_mod.requests = DummyRequests()
    r2 = client.post("/api/log-frontend-error", json={"error_code": "E2"})
    # Should still return 200 because log_error swallows RequestException
    assert r2.status_code == 200
