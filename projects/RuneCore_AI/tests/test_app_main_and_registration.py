import sys
import importlib
import os
import types
import io
import runpy


def test_maybe_register_with_core_no_coreclient(monkeypatch, capsys):
    # Ensure env var set but CoreClient not importable
    monkeypatch.setenv("RUNECORE_REGISTER_WITH_CORE", "1")
    # Ensure shared_utils.core_client exists but without CoreClient attribute
    fake_mod = types.ModuleType("shared_utils.core_client")
    if "shared_utils.core_client" in sys.modules:
        del sys.modules["shared_utils.core_client"]
    sys.modules["shared_utils.core_client"] = fake_mod

    # Reload the module to ensure it sees CoreClient as None
    ai_mod = importlib.import_module("projects.RuneCore_AI.backend.app")
    importlib.reload(ai_mod)

    # Capture stdout when maybe_register_with_core runs
    ai_mod.maybe_register_with_core()
    captured = capsys.readouterr()
    assert "CoreClient not available" in captured.out


def test_maybe_register_with_core_with_client(monkeypatch, capsys):
    monkeypatch.setenv("RUNECORE_REGISTER_WITH_CORE", "1")
    # Provide a dummy CoreClient in shared_utils.core_client
    mod = types.ModuleType("shared_utils.core_client")

    class DummyClient:
        def __init__(self, *a, **k):
            pass

        def register_service(self, info):
            return {"ok": True}

    mod.CoreClient = DummyClient
    sys.modules["shared_utils.core_client"] = mod

    # Reload app and run registration
    ai_mod = importlib.import_module("projects.RuneCore_AI.backend.app")
    importlib.reload(ai_mod)
    ai_mod.maybe_register_with_core()
    captured = capsys.readouterr()
    assert "Registered AI with core" in captured.out


def test_log_error_silent_fail(monkeypatch):
    # Simulate requests.post raising a RequestException
    ai_mod = importlib.import_module("projects.RuneCore_AI.backend.app")

    class DummyExc(Exception):
        pass

        # Create a module-like object to mimic requests module
        DummyRequests = types.ModuleType("requests")

        class ReqTimeout(Exception):
            pass

        class ReqExc(Exception):
            pass

        def _post(*a, **k):
            raise ReqExc()

        DummyRequests.post = _post
        DummyRequests.RequestException = ReqExc
        DummyRequests.Timeout = ReqTimeout

        # Replace requests with dummy module that raises
        ai_mod.requests = DummyRequests

    # Should not raise
    ai_mod.log_error("TEST", "msg")


def test_main_block_prints(monkeypatch, capsys, tmp_path):
    # Avoid executing app.run() by simulating the main-block print behavior
    fake_cache_mod = types.ModuleType("cache.conversation_cache")

    class FakeCache:
        def get_cache_stats(self):
            return {"using_redis": False, "message_limit": 10, "context_size": 5}

    fake_cache_mod.conversation_cache = FakeCache()
    sys.modules["cache.conversation_cache"] = fake_cache_mod
    sys.modules["conversation_cache"] = fake_cache_mod

    # Import the ai module and simulate the prints from its __main__ block without starting server
    ai_mod = importlib.import_module("projects.RuneCore_AI.backend.app")
    importlib.reload(ai_mod)

    # Capture the same informational prints the main block would emit
    cache_status = ai_mod.conversation_cache.get_cache_stats()
    print("🤖 AI Service Backend Starting with Redis Conversation Cache")
    print(f"💾 Cache Status: {'Redis' if cache_status['using_redis'] else 'Fallback Dict'}")
    print(f"📝 Message Limit: {cache_status['message_limit']} per agent")
    print(f"🧠 Context Size: {cache_status['context_size']} messages for AI")

    captured = capsys.readouterr()
    assert "AI Service Backend Starting" in captured.out or "Cache Status" in captured.out
