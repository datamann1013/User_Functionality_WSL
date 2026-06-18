"""
RuneGuard_Insight — Docker Container Metrics Collector

Polls all running Docker containers every COLLECT_INTERVAL seconds and
ships their resource stats to CoreMemory (InfluxDB) via the Core proxy.

Measurement: container_metrics
Tags:
  container_name  — Docker container name
  service_name    — Value of the "com.docker.compose.service" label (if present)
Fields:
  cpu_percent     — CPU usage percentage
  mem_usage_mb    — Memory usage in MB
  mem_limit_mb    — Memory limit in MB
  net_rx_mb       — Total network bytes received (MB)
  net_tx_mb       — Total network bytes transmitted (MB)

Operational endpoints:
  GET /health     — lightweight JSON health (status, version, last_collect_ts,
                    containers_seen). Served on HEALTH_PORT (default 5005).

Environment:
  CORE_PROXY_URL    — CoreMemory telemetry base URL via Core proxy
                      default: http://runecore_core:11441/api/proxy/CoreMemoryAPI
  COLLECT_INTERVAL  — Polling interval in seconds (default: 30)
  HEALTH_PORT       — Port for the /health HTTP server (default: 5005)
  RUNECORE_CORE_URL — Core registry base URL (dev: http://runecore_core:11441)
  RUNEGUARD_LOGGER_URL — RuneGuard Logger /log endpoint
                      default: http://runeguard_logger:5001/log
  HEARTBEAT_INTERVAL — Core heartbeat interval in seconds (default: 30)
"""
import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
import docker

try:  # container layout: /app/shared_utils ; tests: sys.path injection
    from shared_utils.core_client import CoreClient, CoreClientError
except Exception:  # pragma: no cover - import shim
    try:
        from core_client import CoreClient, CoreClientError
    except Exception:
        CoreClient = None
        CoreClientError = Exception

from error_codes import ERROR_CODES  # noqa: F401  (kept for reference/validation)

__version__ = "0.2.0"
SERVICE_NAME = "RuneGuard_Insight"

CORE_PROXY_URL = os.environ.get(
    "CORE_PROXY_URL", "http://runecore_core:11441/api/proxy/CoreMemoryAPI"
)
COLLECT_INTERVAL = int(os.environ.get("COLLECT_INTERVAL", "30"))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "5005"))
RUNECORE_CORE_URL = os.environ.get("RUNECORE_CORE_URL", "http://runecore_core:11441")
RUNEGUARD_LOGGER_URL = os.environ.get(
    "RUNEGUARD_LOGGER_URL", "http://runeguard_logger:5001/log"
)
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))

# Docker socket retry/backoff tuning
DOCKER_MAX_RETRIES = int(os.environ.get("DOCKER_MAX_RETRIES", "3"))
DOCKER_BACKOFF_BASE = float(os.environ.get("DOCKER_BACKOFF_BASE", "1.0"))


# --------------------------------------------------------------------------
# Shared health state (read by the health server, written by the collect loop)
# --------------------------------------------------------------------------
class _HealthState:
    def __init__(self):
        self.lock = threading.Lock()
        self.docker_ok = False
        self.last_collect_ts = None  # epoch seconds of last *successful* collect
        self.containers_seen = 0

    def update(self, *, docker_ok=None, last_collect_ts=None, containers_seen=None):
        with self.lock:
            if docker_ok is not None:
                self.docker_ok = docker_ok
            if last_collect_ts is not None:
                self.last_collect_ts = last_collect_ts
            if containers_seen is not None:
                self.containers_seen = containers_seen

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "status": "healthy" if self.docker_ok else "degraded",
                "version": __version__,
                "last_collect_ts": self.last_collect_ts,
                "containers_seen": self.containers_seen,
            }


HEALTH = _HealthState()


# --------------------------------------------------------------------------
# RuneGuard Logger (best-effort, fire-and-forget)
# --------------------------------------------------------------------------
def log_event(error_code: str, message: str = "", exception: str = "", extra=None):
    """Send a structured log entry to RuneGuard Logger. Never raises."""
    if message == "" and error_code in ERROR_CODES:
        message = ERROR_CODES[error_code]
    payload = {
        "error_code": error_code,
        "message": message,
        "exception": exception,
        "extra": extra or {},
        "service": SERVICE_NAME,
    }
    print(f"[Insight] {error_code} - {message}" + (f" :: {exception}" if exception else ""))
    try:
        requests.post(RUNEGUARD_LOGGER_URL, json=payload, timeout=3)
    except Exception:
        # Logger being down must never affect Insight.
        pass


# --------------------------------------------------------------------------
# Metric computation helpers
# --------------------------------------------------------------------------
def _compute_cpu_percent(stats: dict) -> float:
    """Calculate CPU usage percentage from raw Docker stats."""
    try:
        cpu_delta = (
            stats["cpu_stats"]["cpu_usage"]["total_usage"]
            - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        )
        system_delta = (
            stats["cpu_stats"]["system_cpu_usage"]
            - stats["precpu_stats"]["system_cpu_usage"]
        )
        num_cpus = stats["cpu_stats"].get("online_cpus") or len(
            stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1])
        )
        if system_delta > 0 and cpu_delta >= 0:
            return round((cpu_delta / system_delta) * num_cpus * 100.0, 2)
    except (KeyError, ZeroDivisionError, TypeError):
        pass
    return 0.0


def _compute_mem(stats: dict):
    """Return (usage_mb, limit_mb) from raw Docker stats."""
    try:
        mem = stats["memory_stats"]
        # Docker excludes file cache from "usage" in newer API via cache key
        cache = mem.get("stats", {}).get("cache", 0)
        usage = max(0, mem.get("usage", 0) - cache)
        limit = mem.get("limit", 0)
        return round(usage / 1024 / 1024, 2), round(limit / 1024 / 1024, 2)
    except (KeyError, TypeError):
        return 0.0, 0.0


def _compute_net(stats: dict):
    """Return (rx_mb, tx_mb) from raw Docker stats."""
    try:
        networks = stats.get("networks", {})
        rx = sum(v.get("rx_bytes", 0) for v in networks.values())
        tx = sum(v.get("tx_bytes", 0) for v in networks.values())
        return round(rx / 1024 / 1024, 2), round(tx / 1024 / 1024, 2)
    except (AttributeError, TypeError):
        return 0.0, 0.0


# --------------------------------------------------------------------------
# Docker access with retry/backoff
# --------------------------------------------------------------------------
def _get_containers():
    """
    Connect to the Docker socket and list running containers, with bounded
    retry/backoff. Returns a list of containers, or None on hard failure.
    Never raises — surfaces failure via return value + health state + Logger.
    """
    last_exc = None
    for attempt in range(1, DOCKER_MAX_RETRIES + 1):
        try:
            client = docker.from_env()
            containers = client.containers.list()
            HEALTH.update(docker_ok=True)
            return containers
        except Exception as e:  # docker.errors.DockerException, socket errors, etc.
            last_exc = e
            if attempt < DOCKER_MAX_RETRIES:
                delay = DOCKER_BACKOFF_BASE * (2 ** (attempt - 1))
                log_event("WGID01", exception=str(e),
                          extra={"attempt": attempt, "retry_in_s": delay})
                time.sleep(delay)

    HEALTH.update(docker_ok=False)
    log_event("EGID01", exception=str(last_exc))
    return None


def _collect_and_ship():
    """Single collection cycle: poll all containers and POST batch to CoreMemory.

    Returns the number of containers seen (0 on docker failure). Never raises.
    """
    containers = _get_containers()
    if containers is None:
        return 0

    points = []
    for container in containers:
        try:
            stats = container.stats(stream=False)
        except Exception as e:
            log_event("WGID02", exception=str(e),
                      extra={"container": getattr(container, "name", "?")})
            continue

        name = container.name
        labels = container.labels or {}
        service = labels.get("com.docker.compose.service", name)
        project = labels.get("com.docker.compose.project", "")

        cpu = _compute_cpu_percent(stats)
        mem_usage, mem_limit = _compute_mem(stats)
        net_rx, net_tx = _compute_net(stats)

        points.append({
            "measurement": "container_metrics",
            "tags": {
                "container_name": name,
                "service_name": service,
                "project": project,
            },
            "fields": {
                "cpu_percent": cpu,
                "mem_usage_mb": mem_usage,
                "mem_limit_mb": mem_limit,
                "net_rx_mb": net_rx,
                "net_tx_mb": net_tx,
            },
        })

    # Mark a successful collection cycle (docker was reachable) regardless of
    # whether telemetry shipping below succeeds.
    HEALTH.update(last_collect_ts=time.time(), containers_seen=len(points))

    if not points:
        return 0

    try:
        requests.post(
            f"{CORE_PROXY_URL}/telemetry/batch",
            json={"points": points},
            timeout=10,
        )
        print(f"[Insight] Shipped {len(points)} container metrics")
    except Exception as e:
        log_event("WGIT01", exception=str(e))

    return len(points)


# --------------------------------------------------------------------------
# Health HTTP server (stdlib, daemon thread)
# --------------------------------------------------------------------------
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib naming)
        if self.path.rstrip("/") in ("/health", ""):
            body = json.dumps(HEALTH.snapshot()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):  # silence default stderr access logging
        pass


def start_health_server(port: int = None) -> ThreadingHTTPServer:
    """Start the /health server in a daemon thread. Returns the server."""
    port = HEALTH_PORT if port is None else port
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    except Exception as e:
        log_event("EGIH01", exception=str(e))
        raise
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log_event("IGIH01", extra={"port": port})
    return server


# --------------------------------------------------------------------------
# Core registration + heartbeat (best-effort / limb mode)
# --------------------------------------------------------------------------
def get_container_name() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "runeguard_insight"


def build_registration_payload() -> dict:
    container_name = get_container_name()
    return {
        "name": SERVICE_NAME,
        "version": __version__,
        "rest_url": f"http://{container_name}:{HEALTH_PORT}",
        "health_url": f"http://{container_name}:{HEALTH_PORT}/health",
        "dependencies": [],
        "wishlist": ["CoreMemoryAPI", "RuneGuardLogger"],
        "container_name": container_name,
    }


def register_with_core() -> bool:
    """Register with Core via shared CoreClient. Best-effort, never raises."""
    if CoreClient is None:
        log_event("WGIR01", message="CoreClient unavailable (shared_utils not importable)")
        return False
    try:
        client = CoreClient(core_url=RUNECORE_CORE_URL, disable_mtls=True)
        result = client.register_service(build_registration_payload())
        log_event("IGIR01", extra={"result": result})
        return True
    except Exception as e:  # CoreClientError or anything else
        log_event("WGIR01", exception=str(e))
        return False


def send_heartbeat() -> bool:
    """POST a heartbeat to Core's HA-facing heartbeat endpoint. Never raises."""
    snap = HEALTH.snapshot()
    payload = {
        "name": SERVICE_NAME,
        "status": snap["status"],
        "metadata": {
            "docker_ok": snap["status"] == "healthy",
            "containers_seen": snap["containers_seen"],
            "service_type": "telemetry_collector",
        },
    }
    try:
        resp = requests.post(
            f"{RUNECORE_CORE_URL}/api/v1/services/heartbeat",
            json=payload,
            timeout=5,
        )
        if resp.status_code != 200:
            log_event("WGIR02", message=f"heartbeat status {resp.status_code}")
            return False
        return True
    except Exception as e:
        log_event("WGIR02", exception=str(e))
        return False


def _heartbeat_loop():
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        send_heartbeat()


def start_heartbeat_thread():
    thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    thread.start()
    return thread


# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------
def main():
    log_event("IGI#01", extra={"interval": COLLECT_INTERVAL, "core_proxy": CORE_PROXY_URL})
    print(f"[Insight] Shipping to: {CORE_PROXY_URL}")

    start_health_server()
    register_with_core()        # limb mode — does not block startup
    start_heartbeat_thread()

    # Initial delay to let CoreMemory come up
    time.sleep(5)
    while True:
        _collect_and_ship()
        time.sleep(COLLECT_INTERVAL)


if __name__ == "__main__":
    main()
