import importlib
import sys
import types


def load_ai():
    if "projects.RuneCore_AI.backend.app" in sys.modules:
        del sys.modules["projects.RuneCore_AI.backend.app"]
    ai_mod = importlib.import_module("projects.RuneCore_AI.backend.app")
    importlib.reload(ai_mod)

    class CacheStub:
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

    ai_mod.conversation_cache = CacheStub()
    return ai_mod, ai_mod.app


def test_chat_timeout_path(monkeypatch):
    ai_mod, app = load_ai()
    # Simulate requests.exceptions.Timeout being available and thrown
    class DummyRequests:
        class Timeout(Exception):
            pass

        class RequestException(Exception):
            pass

        def post(self, *a, **k):
            raise DummyRequests.Timeout()
    # Expose exceptions namespace so app code using requests.exceptions.Timeout works
    import types as _types
    DummyRequests.exceptions = _types.SimpleNamespace(Timeout=DummyRequests.Timeout)

    ai_mod.requests = DummyRequests()
    client = app.test_client()
    r = client.post("/api/chat", json={"message": "x" * 200})
    assert r.status_code == 200
    j = r.get_json()
    assert j["mode"] in ("timeout_fallback", "graceful_fallback")


def test_log_error_catches_unexpected_exception(monkeypatch):
    ai_mod, _ = load_ai()

    # Provide a requests-like object that raises a generic exception
    class BadRequests:
        RequestException = Exception
        Timeout = Exception

        def post(self, *a, **k):
            raise RuntimeError("boom")

    ai_mod.requests = BadRequests()
    # Should not raise
    ai_mod.log_error("TEST_ERR", "msg")
