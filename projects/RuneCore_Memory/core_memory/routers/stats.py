"""
Stats router — aggregate metrics about the CoreMemory state.

GET /v1/stats
  Returns memory counts, InfluxDB/Redis availability for the dashboard.
"""
import os
from datetime import datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import func

from ..db import SessionLocal, Memory
from ..influx import is_available as influx_is_available

router = APIRouter()


@router.get("/stats")
def get_stats():
    result = {
        "memories": {"total": 0, "by_namespace": {}},
        "recent_24h": 0,
        "influx_available": False,
        "redis_available": False,
    }

    # PostgreSQL — memory counts
    if SessionLocal:
        db = SessionLocal()
        try:
            result["memories"]["total"] = db.query(Memory).count()

            rows = (
                db.query(Memory.namespace, func.count(Memory.id))
                .group_by(Memory.namespace)
                .all()
            )
            result["memories"]["by_namespace"] = {ns: cnt for ns, cnt in rows}

            cutoff = datetime.utcnow() - timedelta(hours=24)
            result["recent_24h"] = (
                db.query(Memory).filter(Memory.created_at >= cutoff).count()
            )
        except Exception:
            pass
        finally:
            db.close()

    # InfluxDB
    result["influx_available"] = influx_is_available()

    # Redis
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis
            r = redis.from_url(redis_url)
            r.ping()
            result["redis_available"] = True
        except Exception:
            pass

    return result
