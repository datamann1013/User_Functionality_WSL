from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .routers import memories
from .utils import log_exception
import traceback
from fastapi.requests import Request
from fastapi.responses import JSONResponse


app = FastAPI(title="CoreMemory", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(memories.router, prefix="/v1")


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
