"""Smoke tests for RuneGuard_Insight.

Covered:
  - /health returns 200 with a well-formed JSON body
  - the collect loop survives a Docker exception without crashing
  - the Core registration payload is well-formed
"""
import json
import urllib.request


# --------------------------------------------------------------------------
# Health endpoint
# --------------------------------------------------------------------------
def test_health_endpoint_returns_200(insight):
    server = insight.start_health_server(port=0)
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
        assert body["status"] in ("healthy", "degraded")
        assert body["version"] == insight.__version__
        assert "last_collect_ts" in body
        assert "containers_seen" in body
    finally:
        server.shutdown()


def test_health_unknown_path_404(insight):
    server = insight.start_health_server(port=0)
    try:
        port = server.server_address[1]
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
            assert False, "expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()


# --------------------------------------------------------------------------
# Collect loop resilience
# --------------------------------------------------------------------------
def test_collect_handles_docker_exception(insight, monkeypatch):
    # docker.from_env raises every time -> _get_containers exhausts retries.
    import docker

    def boom(*args, **kwargs):
        raise RuntimeError("cannot connect to docker socket")

    monkeypatch.setattr(docker, "from_env", boom)
    # No real sleeping / network during retries.
    monkeypatch.setattr(insight.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(insight, "log_event", lambda *a, **k: None)
    monkeypatch.setattr(insight, "DOCKER_MAX_RETRIES", 2)

    # Must not raise, and must report zero containers.
    result = insight._collect_and_ship()
    assert result == 0
    # Health state flips to degraded after a hard docker failure.
    assert insight.HEALTH.snapshot()["status"] == "degraded"


def test_collect_ships_metrics_on_success(insight, monkeypatch):
    import docker

    fake_stats = {
        "cpu_stats": {"cpu_usage": {"total_usage": 200}, "system_cpu_usage": 2000,
                      "online_cpus": 2},
        "precpu_stats": {"cpu_usage": {"total_usage": 100}, "system_cpu_usage": 1000},
        "memory_stats": {"usage": 1024 * 1024 * 50, "limit": 1024 * 1024 * 100,
                         "stats": {"cache": 0}},
        "networks": {"eth0": {"rx_bytes": 1024 * 1024, "tx_bytes": 1024 * 1024 * 2}},
    }

    class FakeContainer:
        name = "demo"
        labels = {"com.docker.compose.service": "demo_svc",
                  "com.docker.compose.project": "demo_proj"}

        def stats(self, stream=False):
            return fake_stats

    class FakeClient:
        def containers_list(self):
            return [FakeContainer()]

        @property
        def containers(self):
            outer = self

            class _C:
                def list(self):
                    return outer.containers_list()
            return _C()

    monkeypatch.setattr(docker, "from_env", lambda *a, **k: FakeClient())

    captured = {}

    def fake_post(url, json=None, timeout=None, **kwargs):
        captured["url"] = url
        captured["json"] = json

        class R:
            status_code = 200
        return R()

    monkeypatch.setattr(insight.requests, "post", fake_post)

    count = insight._collect_and_ship()
    assert count == 1
    assert captured["url"].endswith("/telemetry/batch")
    point = captured["json"]["points"][0]
    assert point["measurement"] == "container_metrics"
    assert point["tags"]["service_name"] == "demo_svc"
    assert point["fields"]["mem_usage_mb"] == 50.0
    snap = insight.HEALTH.snapshot()
    assert snap["status"] == "healthy"
    assert snap["containers_seen"] == 1


# --------------------------------------------------------------------------
# Core registration payload
# --------------------------------------------------------------------------
def test_registration_payload_well_formed(insight):
    payload = insight.build_registration_payload()
    assert payload["name"] == "RuneGuard_Insight"
    assert payload["version"] == insight.__version__
    assert payload["rest_url"].startswith("http://")
    assert payload["health_url"].endswith("/health")
    assert isinstance(payload["dependencies"], list)
    assert isinstance(payload["wishlist"], list)
    assert payload["container_name"]


def test_register_with_core_is_best_effort(insight, monkeypatch):
    # CoreClient.register_service raises -> register_with_core must swallow it.
    class BoomClient:
        def __init__(self, *a, **k):
            pass

        def register_service(self, info, timeout=5):
            raise RuntimeError("core down")

    monkeypatch.setattr(insight, "CoreClient", BoomClient)
    monkeypatch.setattr(insight, "log_event", lambda *a, **k: None)
    assert insight.register_with_core() is False


def test_send_heartbeat_handles_network_error(insight, monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("no core")

    monkeypatch.setattr(insight.requests, "post", boom)
    monkeypatch.setattr(insight, "log_event", lambda *a, **k: None)
    assert insight.send_heartbeat() is False
