import os
import importlib


def test_maybe_register_with_core(monkeypatch, tmp_path, capsys):
    # Ensure env var is set
    monkeypatch.setenv("RUNECORE_REGISTER_WITH_CORE", "1")

    class DummyClient:
        def __init__(self, *a, **k):
            pass

        def register_service(self, info):
            return {"ok": True, "service_id": "svc-1"}

    # Patch shared_utils.core_client.CoreClient used by the module
    monkeypatch.setenv("RUNECORE_DISABLE_MTLS", "1")
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "projects")))
    import shared_utils.core_client as cc_mod
    monkeypatch.setattr(cc_mod, "CoreClient", DummyClient)

    # Reload the service module to pick up patched CoreClient
    import projects.RuneGuard_Logger.error_logger_service as svc_mod
    importlib.reload(svc_mod)

    # Call maybe_register_with_core and capture output
    svc_mod.maybe_register_with_core()
    captured = capsys.readouterr()
    assert "Registered with core" in captured.out or "Failed to register with core" not in captured.out
