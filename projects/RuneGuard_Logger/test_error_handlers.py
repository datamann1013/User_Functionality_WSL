import types
import traceback
from flask import Flask


def test_get_error_explanation_default():
    from projects.RuneGuard_Logger.error_handler import get_error_explanation

    msg = get_error_explanation("NON_EXISTENT")
    assert "Undefined error code" in msg


def test_flask_error_handler_non_http(monkeypatch):
    # Patch log_error_remote to capture calls
    called = {}

    def fake_log(code, message=None, exception=None):
        called['code'] = code
        called['message'] = message
        called['exception'] = exception

    monkeypatch.setattr('projects.RuneGuard_Logger.error_handler.log_error_remote', fake_log)

    from projects.RuneGuard_Logger.error_handler import flask_error_handler

    class DummyExc(Exception):
        pass

    # Create a fake request context so request.method/path are defined
    app = Flask(__name__)
    with app.test_request_context('/test', method='GET'):
        res = flask_error_handler(DummyExc("boom"))
    assert res[1] == 500
    assert called.get('code') == 'E00000'


def test_log_exceptions_decorator(monkeypatch):
    monkeypatch.setattr('projects.RuneGuard_Logger.error_handler.log_error_remote', lambda *a, **k: None)

    from projects.RuneGuard_Logger.error_handler import log_exceptions

    @log_exceptions('TEST01')
    def will_raise():
        raise ValueError("fail")

    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context('/x', method='POST'):
        res = will_raise()
    assert res[1] == 500


def test_log_python_and_react_exception(monkeypatch):
    calls = []
    monkeypatch.setattr('projects.RuneGuard_Logger.error_handler.log_error_remote', lambda *a, **k: calls.append((a, k)))

    from projects.RuneGuard_Logger.error_handler import log_python_exception, log_react_exception

    # simulate python exception
    try:
        raise RuntimeError("err")
    except RuntimeError as e:
        tb = e.__traceback__
        log_python_exception(type(e), e, tb)

    log_react_exception({"some": "info"})
    assert len(calls) >= 2
