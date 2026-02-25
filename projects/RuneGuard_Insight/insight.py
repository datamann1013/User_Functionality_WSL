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

Environment:
  CORE_PROXY_URL   — CoreMemory telemetry base URL via Core proxy
                     default: http://runecore_core:11441/api/proxy/CoreMemoryAPI
  COLLECT_INTERVAL — Polling interval in seconds (default: 30)
"""
import os
import time
import requests
import docker

CORE_PROXY_URL = os.environ.get(
    "CORE_PROXY_URL", "http://runecore_core:11441/api/proxy/CoreMemoryAPI"
)
COLLECT_INTERVAL = int(os.environ.get("COLLECT_INTERVAL", "30"))


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


def _collect_and_ship():
    """Single collection cycle: poll all containers and POST batch to CoreMemory."""
    try:
        client = docker.from_env()
        containers = client.containers.list()
    except Exception as e:
        print(f"[Insight] Docker error: {e}")
        return

    points = []
    for container in containers:
        try:
            stats = container.stats(stream=False)
        except Exception:
            continue

        name = container.name
        labels = container.labels or {}
        service = labels.get("com.docker.compose.service", name)

        cpu = _compute_cpu_percent(stats)
        mem_usage, mem_limit = _compute_mem(stats)
        net_rx, net_tx = _compute_net(stats)

        points.append({
            "measurement": "container_metrics",
            "tags": {
                "container_name": name,
                "service_name": service,
            },
            "fields": {
                "cpu_percent": cpu,
                "mem_usage_mb": mem_usage,
                "mem_limit_mb": mem_limit,
                "net_rx_mb": net_rx,
                "net_tx_mb": net_tx,
            },
        })

    if not points:
        return

    try:
        requests.post(
            f"{CORE_PROXY_URL}/telemetry/batch",
            json={"points": points},
            timeout=10,
        )
        print(f"[Insight] Shipped {len(points)} container metrics")
    except Exception as e:
        print(f"[Insight] Telemetry POST failed: {e}")


def main():
    print(f"[Insight] RuneGuard_Insight started (interval={COLLECT_INTERVAL}s)")
    print(f"[Insight] Shipping to: {CORE_PROXY_URL}")
    # Initial delay to let CoreMemory come up
    time.sleep(15)
    while True:
        _collect_and_ship()
        time.sleep(COLLECT_INTERVAL)


if __name__ == "__main__":
    main()
