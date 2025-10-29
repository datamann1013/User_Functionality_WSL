import importlib
import sys
import types
import requests
import pytest


from projects.shared_utils.core_client import CoreClient, CoreClientError


class DummyResp:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text or str(self._body)

    def json(self):
        return self._body


def test_register_service_success(monkeypatch):
    def fake_post(url, json=None, headers=None, timeout=None, cert=None, verify=None):
        return DummyResp(200, {"ok": True, "service_id": "s1"})

    monkeypatch.setattr("projects.shared_utils.core_client.requests.post", fake_post)
    cc = CoreClient(core_url="http://core.local")
    res = cc.register_service({"name": "x"})
    assert res.get("ok") is True


def test_register_service_network_error(monkeypatch):
    def fake_post(*a, **k):
        raise requests.RequestException("net")

    monkeypatch.setattr("projects.shared_utils.core_client.requests.post", fake_post)
    cc = CoreClient(core_url="http://core.local")
    with pytest.raises(CoreClientError):
        cc.register_service({"name": "x"})


def test_register_service_invalid_json(monkeypatch):
    class BadResp:
        status_code = 200

        def __init__(self):
            self.text = "not json"

        def json(self):
            raise ValueError("bad json")

    monkeypatch.setattr("projects.shared_utils.core_client.requests.post", lambda *a, **k: BadResp())
    cc = CoreClient(core_url="http://core.local")
    with pytest.raises(CoreClientError) as exc:
        cc.register_service({"name": "x"})
    assert "invalid json" in str(exc.value)


def test_register_service_http_error(monkeypatch):
    monkeypatch.setattr("projects.shared_utils.core_client.requests.post", lambda *a, **k: DummyResp(500, {"error": "x"}))
    cc = CoreClient(core_url="http://core.local")
    with pytest.raises(CoreClientError):
        cc.register_service({"name": "x"})


def test_sign_csr_success(monkeypatch):
    monkeypatch.setattr("projects.shared_utils.core_client.requests.post", lambda *a, **k: DummyResp(200, {"ok": True, "cert_pem": "CERT"}))
    cc = CoreClient(core_url="http://core.local")
    cert = cc.sign_csr("CSRDATA")
    assert cert == "CERT"


def test_sign_csr_network_error(monkeypatch):
    def fake_post(*a, **k):
        raise requests.RequestException("net")

    monkeypatch.setattr("projects.shared_utils.core_client.requests.post", fake_post)
    cc = CoreClient(core_url="http://core.local")
    with pytest.raises(CoreClientError):
        cc.sign_csr("CSR")


def test_sign_csr_invalid_json(monkeypatch):
    class BadResp:
        status_code = 200

        def __init__(self):
            self.text = "not json"

        def json(self):
            raise ValueError("bad json")

    monkeypatch.setattr("projects.shared_utils.core_client.requests.post", lambda *a, **k: BadResp())
    cc = CoreClient(core_url="http://core.local")
    with pytest.raises(CoreClientError):
        cc.sign_csr("CSR")


def test_sign_csr_error_response(monkeypatch):
    monkeypatch.setattr("projects.shared_utils.core_client.requests.post", lambda *a, **k: DummyResp(400, {"ok": False}))
    cc = CoreClient(core_url="http://core.local")
    with pytest.raises(CoreClientError):
        cc.sign_csr("CSR")


def test_disable_mtls_env_override(monkeypatch):
    monkeypatch.setenv("RUNECORE_DISABLE_MTLS", "1")
    cc = CoreClient(cert="c", key="k", ca_path="ca.pem")
    assert cc.cert is None
    assert cc.verify is False
