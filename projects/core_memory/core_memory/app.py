from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .routers import memories

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
