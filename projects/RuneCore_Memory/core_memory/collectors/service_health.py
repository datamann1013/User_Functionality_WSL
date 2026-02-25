"""
Service Health Collector

Runs as a background thread inside CoreMemory.
Every 30s queries Core's service registry and writes a snapshot to InfluxDB.

Measurement: service_health
Tags:  service_name, status
Fields: is_online (0/1), seconds_since_heartbeat
"""
import os
import time
import threading
import requests

from ..influx import get_write_api, INFLUX_BUCKET, INFLUX_ORG

CORE_URL = os.environ.get("RUNECORE_CORE_URL", "")
COLLECT_INTERVAL = int(os.environ.get("SERVICE_HEALTH_INTERVAL", "30"))

_thread = None
_running = False


def _snapshot():
    if not CORE_URL:
        return
    try:
        r = requests.get(f"{CORE_URL}/api/v1/services", timeout=5)
        if not r.ok:
            return
        services = r.json().get("services", [])
    except Exception:
        return

    write_api = get_write_api()
    if write_api is None:
        return

    from influxdb_client import Point

    now_ts = int(time.time())
    points = []
    for svc in services:
        name = svc.get("name", "unknown")
        status = svc.get("status", "unknown")
        last_seen = svc.get("last_seen") or 0
        is_online = 1 if status == "running" else 0
        seconds_since = max(0, now_ts - last_seen) if last_seen else 9999

        points.append(
            Point("service_health")
            .tag("service_name", name)
            .tag("status", status)
            .field("is_online", is_online)
            .field("seconds_since_heartbeat", float(seconds_since))
        )

    if points:
        try:
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
        except Exception as e:
            print(f"[service_health] InfluxDB write failed: {e}")


def _loop():
    global _running
    # Initial delay so InfluxDB has time to be ready
    time.sleep(10)
    while _running:
        try:
            _snapshot()
        except Exception as e:
            print(f"[service_health] unexpected error: {e}")
        time.sleep(COLLECT_INTERVAL)


def start_service_health_collector():
    global _thread, _running
    if _thread and _thread.is_alive():
        return
    _running = True
    _thread = threading.Thread(target=_loop, daemon=True, name="svc-health-collector")
    _thread.start()
    print("[service_health] collector started (30s interval)")


def stop_service_health_collector():
    global _running
    _running = False
