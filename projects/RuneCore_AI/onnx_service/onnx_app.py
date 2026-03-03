#!/usr/bin/env python3
"""
ONNX Service — FastAPI entrypoint
Port: 5006

Serves ONNX models for DirectML/NPU inference.
Exposes an Ollama-compatible chat interface so the ollama_wrapper can treat it
as a second backend alongside Ollama itself.
"""
import os
import logging
import threading
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from model_manager import (
    scan_local_models,
    list_models,
    get_session,
    download_model,
    _registry,
    _registry_lock,
)
from inference import chat_completion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("onnx_service")

ONNX_MODEL_NAME = os.environ.get("ONNX_MODEL_NAME", "")
PORT = int(os.environ.get("PORT", 5006))

app = FastAPI(title="onnx_service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    scan_local_models()
    if ONNX_MODEL_NAME:
        def _eager_load():
            try:
                get_session(ONNX_MODEL_NAME)
            except Exception as e:
                logger.warning("Eager load of %s failed: %s", ONNX_MODEL_NAME, e)

        threading.Thread(target=_eager_load, daemon=True).start()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "onnx_service",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/models")
def get_models():
    return {"models": list_models()}


class ChatRequest(BaseModel):
    model: str
    messages: list
    stream: Optional[bool] = False
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512


@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        model_obj, tokenizer = get_session(req.model)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Model not found: {req.model}")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    try:
        result = chat_completion(
            model_obj,
            tokenizer,
            req.messages,
            temperature=req.temperature,
            max_new_tokens=req.max_tokens,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message": {"role": "assistant", "content": result},
        "done": True,
        "model": req.model,
        "backend": "onnx",
    }


class DownloadRequest(BaseModel):
    model_id: str
    local_name: str


@app.post("/api/models/download")
def trigger_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    # Register immediately so status is visible
    with _registry_lock:
        if req.local_name not in _registry:
            _registry[req.local_name] = {
                "name": req.local_name,
                "model_id": req.model_id,
                "backend": "onnx",
                "status": "queued",
                "size": 0,
                "modified_at": datetime.now().isoformat(),
            }
    background_tasks.add_task(download_model, req.model_id, req.local_name)
    return {"status": "started", "model_id": req.model_id, "local_name": req.local_name}


@app.get("/api/models/download/{local_name}")
def get_download_status(local_name: str):
    with _registry_lock:
        entry = _registry.get(local_name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Model not found: {local_name}")
    return entry


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("onnx_app:app", host="0.0.0.0", port=PORT, reload=False)
