"""
RuneGuard_Dashboard — Backend API

FastAPI service that aggregates monitoring data from CoreMemory (via Core proxy)
and serves it to the React frontend. All data originates from CoreMemory —
no direct access to Core registry, RuneGuard files, or Docker socket.

Endpoints:
  GET /health           — liveness check
  GET /api/services     — service health status (last snapshot per service)
  GET /api/errors       — error stats from RuneGuard (last 24h trend)
  GET /api/memory       — CoreMemory stats (memory counts, DB availability)
  GET /api/containers   — container CPU/RAM usage (last 5 min)

Environment:
  CORE_PROXY_URL — CoreMemory base URL via Core proxy
                   default: http://runecore_core:11441/api/proxy/CoreMemoryAPI
  PORT           — port to listen on (default: 5004)
"""
import os
import socket
import threading
import time

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

CORE_PROXY_URL = os.environ.get(
    "CORE_PROXY_URL", "http://runecore_core:11441/api/proxy/CoreMemoryAPI"
)
RUNECORE_CORE_URL = os.environ.get("RUNECORE_CORE_URL", "http://runecore_core:11441")
_TIMEOUT = 5  # seconds per upstream request

app = FastAPI(title="RuneGuard_Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


# ---------------------------------------------------------------------------
# Core registration
# ---------------------------------------------------------------------------

def _register_with_core():
    if not RUNECORE_CORE_URL:
        return
    payload = {
        "name": "RuneGuardDashboard",
        "version": "0.1.0",
        "rest_url": "http://dashboard_backend:5004",
        "dependencies": [],
        "container_name": socket.gethostname(),
    }
    for attempt in range(5):
        try:
            r = requests.post(
                f"{RUNECORE_CORE_URL}/api/v1/services/register",
                json=payload,
                timeout=5,
            )
            if r.ok:
                print("[Dashboard] Registered with Core")
                return
        except Exception as e:
            print(f"[Dashboard] Registration attempt {attempt + 1} failed: {e}")
        time.sleep(3 * (attempt + 1))
    print("[Dashboard] Could not register with Core after 5 attempts")


@app.on_event("startup")
async def startup():
    threading.Thread(target=_register_with_core, daemon=True).start()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _proxy_get(path: str, default):
    """GET from CoreMemory via proxy, return parsed JSON or default on any error."""
    try:
        r = requests.get(f"{CORE_PROXY_URL}/{path}", timeout=_TIMEOUT)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return default


def _proxy_post(path: str, body: dict, default):
    """POST to CoreMemory via proxy, return parsed JSON or default."""
    try:
        r = requests.post(f"{CORE_PROXY_URL}/{path}", json=body, timeout=_TIMEOUT)
        if r.ok:
            return r.json()
    except Exception:
        pass
    return default


def _last_value_per_tag(results: list, tag_key: str, field_key: str):
    """
    From a flat InfluxDB results list, extract the most recent value for each
    unique tag value. Returns {tag_value: field_value}.
    """
    latest = {}
    for row in results:
        tag_val = row.get("tags", {}).get(tag_key, "unknown")
        if row.get("field") == field_key:
            # Results are ordered by time ascending — last write wins
            latest[tag_val] = row.get("value")
    return latest


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "runeguard_dashboard"}


@app.get("/api/services")
def get_services():
    """
    Returns the last known status for every service.
    Source: InfluxDB measurement 'service_health', last 2 minutes.
    """
    data = _proxy_post(
        "telemetry/query",
        {
            "measurement": "service_health",
            "start": "-2m",
            "limit": 500,
        },
        {"results": []},
    )

    results = data.get("results", [])

    # Build {service_name: {status, is_online, seconds_since_heartbeat}}
    services = {}
    for row in results:
        tags = row.get("tags", {})
        name = tags.get("service_name", "unknown")
        if name not in services:
            services[name] = {
                "name": name,
                "status": tags.get("status", "unknown"),
                "is_online": None,
                "seconds_since_heartbeat": None,
            }
        field = row.get("field")
        if field == "is_online":
            services[name]["is_online"] = row.get("value")
        elif field == "seconds_since_heartbeat":
            services[name]["seconds_since_heartbeat"] = row.get("value")

    return {"services": list(services.values()), "count": len(services)}


@app.get("/api/errors")
def get_errors():
    """
    Returns error stats from RuneGuard over the last 24 hours.
    Source: InfluxDB measurement 'error_stats'.
    """
    data = _proxy_post(
        "telemetry/query",
        {
            "measurement": "error_stats",
            "start": "-24h",
            "limit": 1000,
        },
        {"results": []},
    )

    results = data.get("results", [])
    # Take the latest value for each field (most recent push)
    latest: dict = {}
    for row in results:
        field = row.get("field")
        if field:
            latest[field] = row.get("value", 0)

    return {
        "total_errors": latest.get("total_errors", 0),
        "errors_last_hour": latest.get("errors_last_hour", 0),
        "error_count": latest.get("error_count", 0),
        "warning_count": latest.get("warning_count", 0),
        "info_count": latest.get("info_count", 0),
    }


@app.get("/api/memory")
def get_memory():
    """
    Returns CoreMemory aggregate stats.
    Source: CoreMemory GET /v1/stats (via proxy).
    """
    data = _proxy_get("stats", {
        "memories": {"total": 0, "by_namespace": {}},
        "recent_24h": 0,
        "influx_available": False,
        "redis_available": False,
    })
    return data


@app.get("/api/containers")
def get_containers():
    """
    Returns container resource usage from the last 5 minutes.
    Source: InfluxDB measurement 'container_metrics'.
    """
    data = _proxy_post(
        "telemetry/query",
        {
            "measurement": "container_metrics",
            "start": "-5m",
            "limit": 1000,
        },
        {"results": []},
    )

    results = data.get("results", [])

    # Aggregate latest fields per container
    containers: dict = {}
    for row in results:
        tags = row.get("tags", {})
        name = tags.get("container_name", "unknown")
        if name not in containers:
            containers[name] = {
                "container_name": name,
                "service_name": tags.get("service_name", name),
                "project": tags.get("project", ""),
                "cpu_percent": 0.0,
                "mem_usage_mb": 0.0,
                "mem_limit_mb": 0.0,
                "net_rx_mb": 0.0,
                "net_tx_mb": 0.0,
            }
        field = row.get("field")
        if field in containers[name]:
            containers[name][field] = row.get("value", 0.0)

    return {"containers": list(containers.values()), "count": len(containers)}
