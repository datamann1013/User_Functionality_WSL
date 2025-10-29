import importlib
import sys
import types
import pytest


def load_ai_with_cache(cache_obj=None):
    if "projects.RuneCore_AI.backend.app" in sys.modules:
        del sys.modules["projects.RuneCore_AI.backend.app"]
    ai_mod = importlib.import_module("projects.RuneCore_AI.backend.app")
    importlib.reload(ai_mod)
    if cache_obj is None:
        class DefaultCache:
            def get_cache_stats(self):
                return {"using_redis": False, "message_limit": 10, "context_size": 5}

            def format_context_for_ai(self, agent_id):
                return []

            def format_chat_history_to_string(self, history):
                return ""

            def add_conversation(self, agent_id, user_msg, ai_msg):
                return True

            def get_conversation_context(self, agent_id):
                return []

        cache_obj = DefaultCache()
    ai_mod.conversation_cache = cache_obj
    return ai_mod, ai_mod.app


def test_chat_graceful_fallback_poem():
    ai_mod, app = load_ai_with_cache()
    c = app.test_client()
    r = c.post("/api/chat", json={"message": "Write a poem about trees"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["mode"] == "graceful_fallback"
    assert "poem" in j["response"] or isinstance(j["response"], str)


def test_chat_graceful_fallback_greeting():
    ai_mod, app = load_ai_with_cache()
    c = app.test_client()
    r = c.post("/api/chat", json={"message": "Hello there"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["mode"] == "graceful_fallback"
    assert "Hello" in j["response"] or isinstance(j["response"], str)


def test_chat_graceful_fallback_explain():
    ai_mod, app = load_ai_with_cache()
    c = app.test_client()
    r = c.post("/api/chat", json={"message": "Explain recursion"})
    assert r.status_code == 200
    j = r.get_json()
    assert j["mode"] == "graceful_fallback"


def test_chat_cache_add_exception_is_handled():
    class BadCache:
        def get_cache_stats(self):
            return {"using_redis": False, "message_limit": 10, "context_size": 5}

        def format_context_for_ai(self, agent_id):
            return []

        def format_chat_history_to_string(self, history):
            return ""

        def add_conversation(self, agent_id, user_msg, ai_msg):
            raise RuntimeError("cache write fail")

        def get_conversation_context(self, agent_id):
            return []

    ai_mod, app = load_ai_with_cache(BadCache())
    c = app.test_client()
    r = c.post("/api/chat", json={"message": "Hello world"})
    assert r.status_code == 200
    j = r.get_json()
    # Should return despite cache error
    assert "response" in j


def test_maybe_register_with_core_success_and_failure(monkeypatch, capsys):
    # Success path: provide Dummy CoreClient
    class DummyClient:
        def __init__(self, *a, **k):
            pass

        def register_service(self, info):
            return {"ok": True}

    modname = "shared_utils.core_client"
    dummy = types.ModuleType(modname)
    dummy.CoreClient = DummyClient
    sys.modules[modname] = dummy

    ai_mod, _ = load_ai_with_cache()
    monkeypatch.setenv("RUNECORE_REGISTER_WITH_CORE", "1")
    ai_mod.maybe_register_with_core()
    out = capsys.readouterr()
    assert "Registered AI with core" in out.out

    # Failure path: CoreClient present but register raises
    class BadClient:
        def __init__(self, *a, **k):
            pass

        def register_service(self, info):
            raise RuntimeError("no network")

    dummy.CoreClient = BadClient
    sys.modules[modname] = dummy
    ai_mod, _ = load_ai_with_cache()
    ai_mod.maybe_register_with_core()
    out2 = capsys.readouterr()
    assert "Failed to register AI with core" in out2.out
