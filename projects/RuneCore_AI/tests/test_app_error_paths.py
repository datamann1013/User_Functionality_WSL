import sys
import importlib
import types
import json


def _reload_app_with_cache_module(cache_mod):
    sys.modules["cache.conversation_cache"] = cache_mod
    sys.modules["conversation_cache"] = cache_mod
    app_mod = importlib.import_module("projects.RuneCore_AI.backend.app")
    importlib.reload(app_mod)
    return app_mod


def test_get_cache_stats_error(monkeypatch):
    class BadCache:
        def get_cache_stats(self):
            raise Exception("boom")

    cache_mod = types.ModuleType("cache.conversation_cache")
    cache_mod.conversation_cache = BadCache()

    ai_mod = _reload_app_with_cache_module(cache_mod)
    client = ai_mod.app.test_client()

    r = client.get("/api/cache/stats")
    assert r.status_code == 500
    data = r.get_json()
    assert "Cache stats failed" in data.get("error", "")


def test_get_agent_conversations_cache_error(monkeypatch):
    class BadCache:
        def get_full_conversation(self, agent_id):
            raise Exception("nope")

    cache_mod = types.ModuleType("cache.conversation_cache")
    cache_mod.conversation_cache = BadCache()

    ai_mod = _reload_app_with_cache_module(cache_mod)
    # capture log_error calls
    calls = []

    def fake_log(errcode, msg=None, extra=None):
        calls.append((errcode, msg))

    ai_mod.log_error = fake_log
    client = ai_mod.app.test_client()

    r = client.get("/api/agents/agent-1/conversations")
    # should return 500 and empty conversations per app code
    assert r.status_code == 500
    data = r.get_json()
    assert data["conversations"] == []
    assert any(c[0] == "CACHE_ERROR" for c in calls)


def test_chat_graceful_fallback_variants(monkeypatch):
    # Use a cache that returns empty history
    class OkCache:
        def get_cache_stats(self):
            return {"using_redis": False, "message_limit": 10, "context_size": 5}

        def format_context_for_ai(self, agent_id):
            return []

        def format_chat_history_to_string(self, history):
            return ""

        def add_conversation(self, agent_id, user_msg, ai_msg):
            return

        def get_conversation_context(self, agent_id):
            return []

    cache_mod = types.ModuleType("cache.conversation_cache")
    cache_mod.conversation_cache = OkCache()

    ai_mod = _reload_app_with_cache_module(cache_mod)
    client = ai_mod.app.test_client()

    # Case: Ollama returns non-200, message contains 'poem'
    def bad_post(url, json=None, timeout=None):
        class R:
            status_code = 500

            def json(self):
                return {}

        return R()

    ai_mod.requests.post = bad_post

    r = client.post("/api/chat", json={"message": "Write a poem about stars", "agent_id": "a1"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["mode"] == "graceful_fallback"
    assert "poem" in d["response"].lower() or "poem" in d["response"]

    # Case: question words trigger another branch
    r2 = client.post("/api/chat", json={"message": "Why does sky look blue?", "agent_id": "a1"})
    assert r2.status_code == 200
    d2 = r2.get_json()
    assert d2["mode"] == "graceful_fallback"
    assert "interesting question" in d2["response"].lower() or "technical difficulties" in d2["response"].lower()


def test_cache_add_failure_does_not_break_response(monkeypatch):
    # Cache that raises on add_conversation
    class FlakyCache:
        def get_cache_stats(self):
            return {"using_redis": False, "message_limit": 10, "context_size": 5}

        def format_context_for_ai(self, agent_id):
            return []

        def format_chat_history_to_string(self, history):
            return ""

        def add_conversation(self, agent_id, user_msg, ai_msg):
            raise Exception("disk full")

        def get_conversation_context(self, agent_id):
            return []

    cache_mod = types.ModuleType("cache.conversation_cache")
    cache_mod.conversation_cache = FlakyCache()

    ai_mod = _reload_app_with_cache_module(cache_mod)

    # Make Ollama succeed
    def good_post(url, json=None, timeout=None):
        class R:
            status_code = 200

            def json(self):
                return {"response": "ok"}

        return R()

    ai_mod.requests.post = good_post

    # capture log_error calls
    calls = []

    def fake_log(errcode, msg=None, extra=None):
        calls.append((errcode, msg))

    ai_mod.log_error = fake_log

    client = ai_mod.app.test_client()
    r = client.post("/api/chat", json={"message": "Hi there", "agent_id": "a1"})
    assert r.status_code == 200
    d = r.get_json()
    assert d["response"] == "ok"
    # should have logged cache error
    assert any(c[0] == "CACHE_ERROR" for c in calls)


def test_log_frontend_error_failure(monkeypatch):
    # Send malformed JSON with application/json to trigger request.get_json() error
    ai_mod = importlib.import_module("projects.RuneCore_AI.backend.app")
    importlib.reload(ai_mod)

    client = ai_mod.app.test_client()
    # malformed JSON body
    r = client.post("/api/log-frontend-error", data="{not: json}", content_type="application/json")
    assert r.status_code == 500
    data = r.get_json()
    assert data.get("error") == "Logging failed"
