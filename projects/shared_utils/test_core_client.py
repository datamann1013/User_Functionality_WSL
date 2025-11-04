import pytest
import sys
import os

# Ensure the parent `projects` directory is on sys.path so tests can import the package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared_utils.core_client import CoreClient, CoreClientError


class DummyResp:
    def __init__(self, status_code=200, text='{}', json_obj=None):
        self.status_code = status_code
        self._text = text
        self._json = json_obj

    @property
    def text(self):
        return self._text

    def json(self):
        if self._json is not None:
            return self._json
        raise ValueError("no json")


def test_register_network_error(monkeypatch):
    client = CoreClient(core_url="https://core.test", disable_mtls=True)

    def fake_post(*args, **kwargs):
        raise Exception("conn refused")

    monkeypatch.setattr("requests.post", fake_post)

    with pytest.raises(CoreClientError) as e:
        client.register_service({"name": "svc"})
    assert "network error" in str(e.value)


def test_register_invalid_json(monkeypatch):
    client = CoreClient(core_url="https://core.test", disable_mtls=True)

    def fake_post(*args, **kwargs):
        return DummyResp(status_code=200, text="not-json", json_obj=None)

    monkeypatch.setattr("requests.post", fake_post)

    with pytest.raises(CoreClientError) as e:
        client.register_service({"name": "svc"})
    assert "invalid json response" in str(e.value)


def test_register_core_error(monkeypatch):
    client = CoreClient(core_url="https://core.test", disable_mtls=True)

    def fake_post(*args, **kwargs):
        return DummyResp(status_code=500, text='{"ok": false, "error": "oops"}', json_obj={"ok": False, "error": "oops"})

    monkeypatch.setattr("requests.post", fake_post)

    with pytest.raises(CoreClientError) as e:
        client.register_service({"name": "svc"})
    assert "error from core" in str(e.value)


def test_sign_csr_success(monkeypatch):
    client = CoreClient(core_url="https://core.test", disable_mtls=True)

    def fake_post(*args, **kwargs):
        return DummyResp(status_code=200, text='{"ok": true, "cert_pem": "CERT"}', json_obj={"ok": True, "cert_pem": "CERT"})

    monkeypatch.setattr("requests.post", fake_post)

    cert = client.sign_csr("CSRPEM")
    assert cert == "CERT"
