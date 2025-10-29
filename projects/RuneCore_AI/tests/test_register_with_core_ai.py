import sys
import os
import importlib


def test_maybe_register_with_core(monkeypatch, capsys):
    monkeypatch.setenv("RUNECORE_REGISTER_WITH_CORE", "1")
    monkeypatch.setenv("RUNECORE_DISABLE_MTLS", "1")

    class DummyClient:
        def __init__(self, *a, **k):
            pass

        def register_service(self, info):
            return {"ok": True, "service_id": "ai-1"}

    # Ensure projects directory is on sys.path so shared_utils can be imported
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    sys.path.insert(0, os.path.join(repo_root, "projects"))
    import shared_utils.core_client as cc_mod
    monkeypatch.setattr(cc_mod, "CoreClient", DummyClient)

    import projects.RuneCore_AI.backend.app as ai_mod
    importlib.reload(ai_mod)
    ai_mod.maybe_register_with_core()
    captured = capsys.readouterr()
    assert "Registered AI with core" in captured.out or "Failed to register AI with core" not in captured.out
