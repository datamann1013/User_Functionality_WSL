"""
InfluxDB v2 client wrapper for CoreMemory.

Provides lazy initialization with graceful fallback when InfluxDB is not available.
Configuration via environment variables:
  INFLUX_URL    — InfluxDB v2 URL (default: http://influx:8086)
  INFLUX_TOKEN  — Auth token (default: runecore-dev-token)
  INFLUX_ORG    — Organisation name (default: runecore)
  INFLUX_BUCKET — Default bucket for telemetry (default: telemetry)
"""
import os

INFLUX_URL = os.environ.get("INFLUX_URL", "http://influx:8086")
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN", "runecore-dev-token")
INFLUX_ORG = os.environ.get("INFLUX_ORG", "runecore")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET", "telemetry")

_client = None
_write_api = None
_query_api = None


def _init():
    global _client, _write_api, _query_api
    if _client is not None:
        return True
    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS

        _client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        _write_api = _client.write_api(write_options=SYNCHRONOUS)
        _query_api = _client.query_api()
        return True
    except Exception as e:
        print(f"⚠️  InfluxDB init failed: {e}")
        return False


def get_write_api():
    if _write_api is not None:
        return _write_api
    _init()
    return _write_api


def get_query_api():
    if _query_api is not None:
        return _query_api
    _init()
    return _query_api


def is_available() -> bool:
    """Check if InfluxDB is reachable. Initialises the client as a side-effect."""
    try:
        if not _init():
            return False
        _client.ping()
        return True
    except Exception:
        return False
