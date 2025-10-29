import importlib
import types
from flask import Request


def test_error_handler_and_decorator(monkeypatch):
    eh_mod = importlib.import_module("projects.RuneGuard_Logger.error_handler_optimized")
    importlib.reload(eh_mod)

    # Replace log_error_remote with a spy
    calls = []

    def fake_remote(code, message=None, exception=None):
        calls.append((code, message))

    eh_mod.log_error_remote = fake_remote

    # Simulate non-HTTPException error inside a Flask request context
    from flask import Flask

    app = Flask(__name__)

    class E(Exception):
        pass

    with app.test_request_context("/x", method="POST"):
        resp = eh_mod.flask_error_handler(E())
        assert resp[1] == 500
        assert any(c[0] == "E00000" for c in calls) or len(calls) >= 1

    # Test decorator wraps and returns expected tuple on exception (inside context)
    @eh_mod.log_exceptions("E123")
    def boom():
        raise Exception("boom")

    with app.test_request_context("/boom", method="GET"):
        r = boom()
        assert r[1] == 500
        assert any(c[0] == "E123" for c in calls)
