import os
import sys
import types
import json

import pytest

# ensure imports
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import importlib.util

spec = importlib.util.spec_from_file_location('core_memory.client', os.path.join(ROOT, 'client.py'))
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class DummyResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data or {"ok": True}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._data


def test_create_memory_success(monkeypatch):
    called = {}

    def fake_post(url, json=None, timeout=None):
        called['url'] = url
        called['payload'] = json
        return DummyResponse(200, {"id": "m1", "text": json.get('text')})

    monkeypatch.setattr(client, 'requests', types.SimpleNamespace(post=fake_post))
    res = client.create_memory("hello", agent_id="a1")
    assert res["id"] == "m1"
    assert called['payload']['text'] == "hello"


def test_query_memories_success(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        return DummyResponse(200, {"results": [{"id": "m1", "snippet": "s"}]})

    monkeypatch.setattr(client, 'requests', types.SimpleNamespace(post=fake_post))
    out = client.query_memories(q="x")
    assert isinstance(out, dict)
    assert "results" in out


def test_maybe_register_with_core_no_env(monkeypatch, capsys):
    # ensure env not set
    monkeypatch.delenv('RUNECORE_REGISTER_WITH_CORE', raising=False)
    # call should be a no-op
    client.maybe_register_with_core()
    captured = capsys.readouterr()
    assert captured.out == ""


def test_maybe_register_with_core_with_coreclient(monkeypatch):
    monkeypatch.setenv('RUNECORE_REGISTER_WITH_CORE', '1')
    # provide a fake CoreClient that records register_service
    class FakeCC:
        def __init__(self, core_url=None, disable_mtls=False):
            self.core_url = core_url
            self.disable_mtls = disable_mtls

        def register_service(self, info):
            return {"registered": True, "name": info.get('name')}

    # inject FakeCC into the client module directly
    monkeypatch.setattr(client, 'CoreClient', FakeCC, raising=False)
    monkeypatch.setenv('RUNECORE_CORE_URL', 'http://core')
    monkeypatch.setenv('RUNECORE_DISABLE_MTLS', '1')
    client.maybe_register_with_core()
