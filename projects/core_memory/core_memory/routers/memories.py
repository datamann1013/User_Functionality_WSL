from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict
import uuid
from datetime import datetime
from ..utils import log_error_remote

router = APIRouter()

# In-memory store for scaffold (id -> record)
_STORE: Dict[str, Dict] = {}


class MemoryCreate(BaseModel):
    namespace: Optional[str] = Field(default="global")
    agent_id: Optional[str]
    text: str
    metadata: Optional[Dict] = Field(default_factory=dict)


class MemoryOut(BaseModel):
    id: str
    namespace: str
    agent_id: Optional[str]
    text: str
    metadata: Dict
    created_at: datetime


@router.post("/memories", response_model=MemoryOut)
def create_memory(payload: MemoryCreate):
    try:
        mid = str(uuid.uuid4())
        now = datetime.utcnow()
        record = {
            "id": mid,
            "namespace": payload.namespace,
            "agent_id": payload.agent_id,
            "text": payload.text,
            "metadata": payload.metadata,
            "created_at": now,
        }
        _STORE[mid] = record
        return record
    except Exception as e:
        # Log unexpected to ErrorLogger service
        log_error_remote("CM001", str(e))
        raise HTTPException(status_code=500, detail="Failed to create memory")


@router.get("/memories/{memory_id}", response_model=MemoryOut)
def get_memory(memory_id: str):
    rec = _STORE.get(memory_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Memory not found")
    return rec
