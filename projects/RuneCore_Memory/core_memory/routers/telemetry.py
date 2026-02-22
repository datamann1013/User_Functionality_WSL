"""
Telemetry router — InfluxDB v2 write/query endpoints.

Used by RunePulse Sentinel and other services to store and retrieve time-series data.

Endpoints:
  POST /v1/telemetry        — write one or more data points
  POST /v1/telemetry/query  — query time-series data with Flux
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from ..influx import get_write_api, get_query_api, INFLUX_BUCKET, INFLUX_ORG

router = APIRouter()


class TelemetryPoint(BaseModel):
    measurement: str
    tags: Optional[Dict[str, str]] = None
    fields: Dict[str, Any]
    # ISO 8601 timestamp string or None to use server time
    timestamp: Optional[str] = None


class TelemetryBatch(BaseModel):
    points: List[TelemetryPoint]


class TelemetryQuery(BaseModel):
    measurement: str
    start: Optional[str] = "-1h"   # InfluxDB duration or RFC3339
    stop: Optional[str] = "now()"
    filters: Optional[Dict[str, str]] = None  # tag filters
    limit: Optional[int] = 200


def _build_point(point: TelemetryPoint):
    from influxdb_client import Point as InfluxPoint

    p = InfluxPoint(point.measurement)
    for k, v in (point.tags or {}).items():
        p = p.tag(k, str(v))
    for k, v in point.fields.items():
        # InfluxDB requires numeric or string field values
        if isinstance(v, bool):
            p = p.field(k, int(v))
        else:
            p = p.field(k, v)
    if point.timestamp:
        p = p.time(point.timestamp)
    return p


@router.post("/telemetry")
def write_telemetry(point: TelemetryPoint):
    """Write a single telemetry data point to InfluxDB."""
    write_api = get_write_api()
    if write_api is None:
        raise HTTPException(status_code=503, detail="InfluxDB not available")
    try:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=_build_point(point))
        return {"status": "written", "measurement": point.measurement}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Write failed: {e}")


@router.post("/telemetry/batch")
def write_telemetry_batch(batch: TelemetryBatch):
    """Write multiple telemetry data points in a single request."""
    write_api = get_write_api()
    if write_api is None:
        raise HTTPException(status_code=503, detail="InfluxDB not available")
    if not batch.points:
        return {"status": "ok", "written": 0}
    try:
        records = [_build_point(p) for p in batch.points]
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=records)
        return {"status": "written", "written": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch write failed: {e}")


@router.post("/telemetry/query")
def query_telemetry(req: TelemetryQuery):
    """Query time-series data from InfluxDB using Flux."""
    query_api = get_query_api()
    if query_api is None:
        raise HTTPException(status_code=503, detail="InfluxDB not available")

    # Build optional tag filter clauses
    filter_clause = ""
    if req.filters:
        parts = [f'r["{k}"] == "{v}"' for k, v in req.filters.items()]
        filter_clause = "\n  |> filter(fn: (r) => " + " and ".join(parts) + ")"

    flux = (
        f'from(bucket: "{INFLUX_BUCKET}")\n'
        f'  |> range(start: {req.start}, stop: {req.stop})\n'
        f'  |> filter(fn: (r) => r._measurement == "{req.measurement}")'
        f"{filter_clause}\n"
        f"  |> limit(n: {req.limit})"
    )

    try:
        tables = query_api.query(flux, org=INFLUX_ORG)
        results = []
        for table in tables:
            for record in table.records:
                results.append({
                    "time": record.get_time().isoformat() if record.get_time() else None,
                    "measurement": record.get_measurement(),
                    "field": record.get_field(),
                    "value": record.get_value(),
                    "tags": {
                        k: v for k, v in record.values.items()
                        if not k.startswith("_") and k not in ("result", "table")
                    },
                })
        return {"results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")
