from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .routers import memories
from .utils import log_exception
import traceback
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from . import service_discovery
import os


app = FastAPI(title="CoreMemory", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(memories.router, prefix="/v1")


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    print("🗄️  CoreMemory API Starting")
    
    # Register with Core if configured
    core_url = os.environ.get("RUNECORE_CORE_URL")
    if core_url:
        print(f"📍 Core URL: {core_url}")
        result = service_discovery.register_with_core()
        
        if result.get("registered"):
            print("✅ Registered with Core")
            # Start heartbeat thread
            service_discovery.start_heartbeat_thread()
        else:
            print(f"⚠️  Registration failed: {result.get('reason', 'unknown')}")
    else:
        print("📍 Running in standalone mode (no Core URL)")
    
    # Check database connection
    try:
        from .db import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        print("✅ PostgreSQL connected")
    except Exception as e:
        print(f"⚠️  PostgreSQL connection failed: {e}")
    
    # Check Redis connection
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis
            r = redis.from_url(redis_url)
            r.ping()
            print("✅ Redis connected")
        except Exception as e:
            print(f"⚠️  Redis connection failed: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    service_discovery.stop_heartbeat_thread()


@app.get("/v1/health")
def health():
    return {"status": "ok", "service": "core_memory"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    try:
        # Best-effort log to ErrorLogger
        log_exception("ECM3", exc, extra={"path": str(request.url)})
    except Exception:
        pass
    return JSONResponse(status_code=500, content={"error": "Internal server error", "error_code": "ECM3"})
