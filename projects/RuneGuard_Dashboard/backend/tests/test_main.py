"""
Tests for the RuneGuard_Dashboard backend API.

Uses FastAPI's TestClient. The upstream CoreMemory calls (via the Core proxy)
go through the module-level ``requests`` object in ``main``, which we monkeypatch
so tests are hermetic and never touch the network.

The TestClient is created WITHOUT entering its context manager, so FastAPI
startup events (the best-effort Core registration thread) do not fire.
"""
import os
import sys
import types

import pytest
from fastapi.testclient import TestClient

# Ensure the backend package dir (parent of tests/) is importable.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import main  # noqa: E402

client = TestClient(main.app)


class DummyResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data if data is not None else {}

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._data


def _patch_requests(monkeypatch, *, get=None, post=None):
    """Replace main.requests with a stub exposing get/post."""
    def _default(*_a, **_k):
        return DummyResponse(200, {})

    monkeypatch.setattr(
        main,
        "requests",
        types.SimpleNamespace(get=get or _default, post=post or _default),
    )


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "runeguard_dashboard"


# ---------------------------------------------------------------------------
# /api/services — aggregation when CoreMemory responds
# ---------------------------------------------------------------------------

def test_services_aggregates_telemetry(monkeypatch):
    payload = {
        "results": [
            {"tags": {"service_name": "core", "status": "online"},
             "field": "is_online", "value": 1},
            {"tags": {"service_name": "core", "status": "online"},
             "field": "seconds_since_heartbeat", "value": 3},
        ]
    }

    def fake_post(url, json=None, timeout=None):
        assert url.endswith("/telemetry/query")
        return DummyResponse(200, payload)

    _patch_requests(monkeypatch, post=fake_post)

    resp = client.get("/api/services")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    svc = body["services"][0]
    assert svc["name"] == "core"
    assert svc["is_online"] == 1
    assert svc["seconds_since_heartbeat"] == 3


# ---------------------------------------------------------------------------
# /api/memory — passthrough of CoreMemory stats
# ---------------------------------------------------------------------------

def test_memory_passes_through_stats(monkeypatch):
    stats = {
        "memories": {"total": 42, "by_namespace": {"machine_profile": 2}},
        "recent_24h": 5,
        "influx_available": True,
        "redis_available": True,
    }

    def fake_get(url, timeout=None):
        assert url.endswith("/stats")
        return DummyResponse(200, stats)

    _patch_requests(monkeypatch, get=fake_get)

    resp = client.get("/api/memory")
    assert resp.status_code == 200
    assert resp.json() == stats


# ---------------------------------------------------------------------------
# /api/errors — latest-field reduction
# ---------------------------------------------------------------------------

def test_errors_reduces_latest_fields(monkeypatch):
    payload = {
        "results": [
            {"field": "total_errors", "value": 10},
            {"field": "errors_last_hour", "value": 2},
            {"field": "total_errors", "value": 11},  # newer wins
        ]
    }
    _patch_requests(
        monkeypatch,
        post=lambda url, json=None, timeout=None: DummyResponse(200, payload),
    )

    resp = client.get("/api/errors")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_errors"] == 11
    assert body["errors_last_hour"] == 2
    # Fields not present default to 0
    assert body["warning_count"] == 0


# ---------------------------------------------------------------------------
# Graceful degradation when CoreMemory is unreachable
# ---------------------------------------------------------------------------

def test_services_graceful_when_corememory_down(monkeypatch):
    def boom(*_a, **_k):
        raise ConnectionError("CoreMemory unreachable")

    _patch_requests(monkeypatch, get=boom, post=boom)

    resp = client.get("/api/services")
    assert resp.status_code == 200
    body = resp.json()
    assert body["services"] == []
    assert body["count"] == 0


def test_memory_graceful_when_corememory_down(monkeypatch):
    def boom(*_a, **_k):
        raise ConnectionError("CoreMemory unreachable")

    _patch_requests(monkeypatch, get=boom, post=boom)

    resp = client.get("/api/memory")
    assert resp.status_code == 200
    body = resp.json()
    # Falls back to the documented default shape
    assert body["memories"]["total"] == 0
    assert body["influx_available"] is False


def test_errors_graceful_when_corememory_returns_error(monkeypatch):
    # Upstream returns 5xx — _proxy_post falls back to default
    _patch_requests(
        monkeypatch,
        post=lambda *_a, **_k: DummyResponse(503, {"error": "down"}),
    )

    resp = client.get("/api/errors")
    assert resp.status_code == 200
    assert resp.json()["total_errors"] == 0
