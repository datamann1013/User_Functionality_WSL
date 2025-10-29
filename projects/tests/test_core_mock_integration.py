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

    app.run(port=port, debug=False, use_reloader=False)


def test_core_client_against_mock(monkeypatch):
    # Start mock core server in background thread
    port = 5009
    t = threading.Thread(target=run_mock_core, kwargs={'port': port}, daemon=True)
    t.start()
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
