import importlib
import sys
import runpy
import types
import os


def test_main_block_runs_without_starting_server(monkeypatch, tmp_path):
    modname = "projects.RuneGuard_Logger.error_logger_service"
    # Ensure fresh import
    if modname in sys.modules:
        del sys.modules[modname]

    # Monkeypatch Flask.run to no-op before running module as __main__
    import flask.app

    def fake_run(self, *a, **k):
        # do not block
        return None

    monkeypatch.setattr(flask.app.Flask, "run", fake_run)

    # Set argv to include --port to exercise argparse parsing
    monkeypatch.setattr(sys, "argv", ["error_logger_service.py", "--port", "5005"])

    # Also ensure logs dir points to tmp
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    # Run module as __main__ (should call app.run but our fake avoids blocking)
    runpy.run_module(modname, run_name="__main__")


def test_maybe_register_with_core_success_and_failure(monkeypatch, capsys):
    # Prepare dummy core client module before importing the service so import-time try/except finds it
    dummy_mod = types.ModuleType("shared_utils.core_client")

    class DummyClient:
        def __init__(self, *a, **k):
            pass

        def register_service(self, info):
            return {"ok": True}

    dummy_mod.CoreClient = DummyClient
    sys.modules["shared_utils.core_client"] = dummy_mod

    modname = "projects.RuneGuard_Logger.error_logger_service"
    if modname in sys.modules:
        del sys.modules[modname]
    svc = importlib.import_module(modname)
    importlib.reload(svc)

    monkeypatch.setenv("RUNECORE_REGISTER_WITH_CORE", "1")
    svc.maybe_register_with_core()
    out = capsys.readouterr()
    assert "Registered with core" in out.out

    # Failure path: replace CoreClient with one that raises
    class BadClient:
        def __init__(self, *a, **k):
            pass

        def register_service(self, info):
            raise RuntimeError("nope")

    dummy_mod.CoreClient = BadClient
    sys.modules["shared_utils.core_client"] = dummy_mod
    # Reload service so it picks up changes
    importlib.reload(svc)
    svc.maybe_register_with_core()
    out2 = capsys.readouterr()
    assert "Failed to register with core" in out2.out
