import json
import types
import pytest


def make_app(monkeypatch):
    # Import the app module fresh
    import importlib, sys
    if "projects.RuneCore_AI.backend.app" in sys.modules:
        del sys.modules["projects.RuneCore_AI.backend.app"]
    ai_mod = importlib.import_module("projects.RuneCore_AI.backend.app")
    # Ensure conversation_cache is a simple object with required methods
    class SimpleCache:
        def get_cache_stats(self):
            return {"using_redis": False, "message_limit": 10, "context_size": 5}

        def format_context_for_ai(self, agent_id):
            return []

        def format_chat_history_to_string(self, history):
            return "".join([h.get("content", "") for h in history])

        def add_conversation(self, agent_id, user_msg, ai_msg):
            return True

        def get_conversation_context(self, agent_id):
            return []

    ai_mod.conversation_cache = SimpleCache()
    return ai_mod.app, ai_mod


def test_chat_missing_message(monkeypatch):
    app, ai_mod = make_app(monkeypatch)
    client = app.test_client()
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data.get("error") == "Message is required"


def test_chat_ollama_success(monkeypatch):
    app, ai_mod = make_app(monkeypatch)

    # Simulate a successful ollama response
    class DummyResp:
        status_code = 200

        def json(self):
            return {"response": "Hello from Ollama"}

    def fake_post(url, json=None, timeout=None):
        return DummyResp()

    ai_mod.requests.post = fake_post
    client = app.test_client()
    resp = client.post("/api/chat", json={"message": "hi"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("response") == "Hello from Ollama"
    assert data.get("mode") in ("ollama", "ollama_powered", "ollama")


def test_chat_ollama_timeout_fallback(monkeypatch):
    app, ai_mod = make_app(monkeypatch)

    def fake_post(url, json=None, timeout=None):
        raise ai_mod.requests.exceptions.Timeout()

    # Ensure exceptions exist on the requests module
    if not hasattr(ai_mod.requests, "exceptions"):
        exc_mod = types.SimpleNamespace(Timeout=Exception)
        ai_mod.requests.exceptions = exc_mod

    ai_mod.requests.post = fake_post
    client = app.test_client()
    resp = client.post("/api/chat", json={"message": "hello how are you"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data.get("mode") in ("timeout_fallback", "graceful_fallback")


def test_chat_ollama_error_graceful(monkeypatch):
    app, ai_mod = make_app(monkeypatch)

    def fake_post(url, json=None, timeout=None):
        class BadResp:
            status_code = 500

            def json(self):
                return {}

        return BadResp()

    ai_mod.requests.post = fake_post
    client = app.test_client()
    resp = client.post("/api/chat", json={"message": "tell me a poem"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "response" in data
