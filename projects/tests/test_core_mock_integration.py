import threading
import time
import os
import sys
import requests
from flask import Flask, request, jsonify


def run_mock_core(port=5009):
    app = Flask("mock_core")

    @app.route('/api/v1/services/register', methods=['POST'])
    def register():
        data = request.get_json(force=True)
        if not data.get('name'):
            return jsonify({'ok': False, 'error': 'missing name'}), 400
        return jsonify({'ok': True, 'service_id': 'mock-svc-1'})

    @app.route('/api/v1/pki/sign', methods=['POST'])
    def sign():
        data = request.get_json(force=True)
        csr = data.get('csr_pem')
        if not csr:
            return jsonify({'ok': False, 'error': 'missing csr'}), 400
        return jsonify({'ok': True, 'cert_pem': 'CERTDATA'})

    # Use a WSGI server that can be shut down cleanly from tests
    from werkzeug.serving import make_server

    server = make_server('127.0.0.1', port, app)
    # Start the server in a daemon thread so this helper never blocks the caller.
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    # Give the server a short moment to start
    time.sleep(0.1)
    return server, server_thread


def test_core_client_against_mock(monkeypatch):
    # Start mock core server in background thread using make_server so we can shut it down
    port = 5009
    from werkzeug.serving import make_server

    app = Flask("mock_core")

    @app.route('/api/v1/services/register', methods=['POST'])
    def register_local():
        data = request.get_json(force=True)
        if not data.get('name'):
            return jsonify({'ok': False, 'error': 'missing name'}), 400
        return jsonify({'ok': True, 'service_id': 'mock-svc-1'})

    @app.route('/api/v1/pki/sign', methods=['POST'])
    def sign_local():
        data = request.get_json(force=True)
        csr = data.get('csr_pem')
        if not csr:
            return jsonify({'ok': False, 'error': 'missing csr'}), 400
        return jsonify({'ok': True, 'cert_pem': 'CERTDATA'})

    server = make_server('127.0.0.1', port, app)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    # Ensure shared_utils package is importable from workspace
    import sys, os, importlib
    # tests/ is inside projects/, so the parent directory is the projects/ package root
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    # Remove any injected/shared module so we import a fresh implementation
    if "shared_utils.core_client" in sys.modules:
        del sys.modules["shared_utils.core_client"]
    # Configure core client to point to mock
    from shared_utils.core_client import CoreClient
    # Ensure the core_client module uses the real requests implementation
    import requests as _real_requests, importlib
    try:
        importlib.reload(_real_requests)
    except Exception:
        pass
    import shared_utils.core_client as _cc_mod
    _cc_mod.requests = _real_requests

    cc = CoreClient(core_url=f"http://127.0.0.1:{port}", disable_mtls=True)
    res = cc.register_service({'name': 'test-svc'})
    assert res.get('ok') is True

    cert = cc.sign_csr('CSRDATA')
    assert cert == 'CERTDATA'
    # Shutdown server
    server.shutdown()
    server_thread.join(timeout=1)
