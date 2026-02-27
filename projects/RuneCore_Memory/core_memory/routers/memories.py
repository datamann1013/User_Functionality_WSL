from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import uuid
import json
from datetime import datetime
from ..utils import log_error_remote, log_exception
from ..db import SessionLocal, Memory, init_db, Embedding
import hashlib
import numpy as np

_MEMORY_TTL = 3600   # 1 hour for individual memory entries
_QUERY_TTL  = 300    # 5 minutes for query result sets

def _qkey(namespace: str, q: str, top_k: int) -> str:
    return f"query:{hashlib.md5(f'{namespace}:{q}:{top_k}'.encode()).hexdigest()}"


def _text_to_vector(text: str, dim: int = 64):
    # deterministic hash-based pseudo-embedding for scaffold/testing only
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = [b for b in h]
    arr = np.array(vals, dtype=float)
    if len(arr) < dim:
        arr = np.pad(arr, (0, dim - len(arr)), constant_values=0.0)
    return arr[:dim]
import redis
import os

# Initialize DB if configured
try:
    init_db()
except Exception:
    pass

# Redis client (optional)
REDIS_URL = os.environ.get("REDIS_URL")
_redis = None
if REDIS_URL:
    try:
        _redis = redis.from_url(REDIS_URL)
    except Exception:
        _redis = None

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
    # Persist to Postgres when available
    if SessionLocal:
        db = SessionLocal()
        try:
            mem = Memory(
                namespace=payload.namespace,
                agent_id=payload.agent_id,
                text=payload.text,
                metadata=payload.metadata,
            )
            db.add(mem)
            db.commit()
            db.refresh(mem)
            # compute deterministic embedding (fallback) and store
            try:
                vec = _text_to_vector(payload.text)
                emb = Embedding(memory_id=mem.id, vector=list(vec))
                db.add(emb)
                db.commit()
            except Exception:
                # embedding failure shouldn't prevent creation
                db.rollback()
            result = {
                "id": str(mem.id),
                "namespace": mem.namespace,
                "agent_id": mem.agent_id,
                "text": mem.text,
                "metadata": getattr(mem, "metadata_json", {}) or {},
                "created_at": mem.created_at,
            }
            # cache in redis (best-effort, with TTL)
            try:
                if _redis:
                    _redis.set(f"memory:{result['id']}", result['text'], ex=_MEMORY_TTL)
            except Exception:
                pass
            return result
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            log_exception("ECM1", e, extra={"payload": payload.dict()})
            raise HTTPException(status_code=500, detail="Failed to create memory")
        finally:
            db.close()
    else:
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
            log_exception("ECM1", e, extra={"payload": payload.dict()})
            raise HTTPException(status_code=500, detail="Failed to create memory")


@router.get("/memories/{memory_id}", response_model=MemoryOut)
def get_memory(memory_id: str):
    # Try Redis cache first
    try:
        if _redis:
            cached = _redis.get(f"memory:{memory_id}")
            if cached:
                _redis.expire(f"memory:{memory_id}", _MEMORY_TTL)
                return {
                    "id": memory_id,
                    "namespace": "global",
                    "agent_id": None,
                    "text": cached.decode("utf-8"),
                    "metadata": {},
                    "created_at": datetime.utcnow(),
                }
    except Exception:
        pass

    if SessionLocal:
        db = SessionLocal()
        try:
            mem = db.query(Memory).filter(Memory.id == memory_id).first()
            if not mem:
                log_error_remote("ECM2", f"Memory not found: {memory_id}", extra={"memory_id": memory_id}, severity="warning")
                raise HTTPException(status_code=404, detail="Memory not found")
            return {
                "id": str(mem.id),
                "namespace": mem.namespace,
                "agent_id": mem.agent_id,
                "text": mem.text,
                "metadata": getattr(mem, "metadata_json", {}) or {},
                "created_at": mem.created_at,
            }
        except HTTPException:
            raise
        except Exception as e:
            log_exception("ECM2", e, extra={"memory_id": memory_id})
            raise HTTPException(status_code=500, detail="Failed to retrieve memory")
        finally:
            db.close()
    else:
        rec = _STORE.get(memory_id)
        if not rec:
            log_error_remote("ECM2", f"Memory not found: {memory_id}", extra={"memory_id": memory_id}, severity="warning")
            raise HTTPException(status_code=404, detail="Memory not found")
        return rec


class QueryRequest(BaseModel):
    q: Optional[str] = None
    embedding: Optional[List[float]] = None
    namespace: Optional[str] = Field(default="global")
    top_k: Optional[int] = Field(default=5)


@router.post("/memories/query")
def query_memories(req: QueryRequest):
    # If vector search requested and embedding present, use pgvector (placeholder)
    results = []
    try:
        # Check query cache (only for text queries — embeddings are too variable)
        if _redis and not req.embedding:
            cache_key = _qkey(req.namespace or "global", req.q or "", req.top_k or 5)
            cached = _redis.get(cache_key)
            if cached:
                return {"results": json.loads(cached)}

        if req.embedding and SessionLocal:
            # Placeholder: perform vector similarity query if pgvector available
            db = SessionLocal()
            # Real implementation: use pgvector operator <-> and order by distance
            # Fallback: load all embeddings and compute cosine similarity
            embs = db.query(Embedding).all()
            target = np.array(req.embedding)
            scored = []
            for e in embs:
                vec = np.array(e.vector)
                score = float(np.dot(target, vec) / (np.linalg.norm(target) * np.linalg.norm(vec) + 1e-10))
                scored.append((str(e.memory_id), score))
            scored.sort(key=lambda x: x[1], reverse=True)
            for mid, sc in scored[: req.top_k]:
                m = db.query(Memory).filter(Memory.id == mid).first()
                results.append({
                    "id": str(m.id),
                    "score": sc,
                    "text": m.text,
                    "snippet": m.text[:200],
                    "metadata": getattr(m, "metadata_json", {}) or {},
                })
        else:
            if SessionLocal:
                db = SessionLocal()
                q = (db.query(Memory)
                     .filter(Memory.namespace == req.namespace)
                     .limit(req.top_k)
                     .all())
                for r in q:
                    results.append({
                        "id": str(r.id),
                        "score": 0.0,
                        "text": r.text,
                        "snippet": r.text[:200],
                        "metadata": getattr(r, "metadata_json", {}) or {},
                    })
            else:
                for _, r in _STORE.items():
                    if r["namespace"] == req.namespace:
                        results.append({"id": r["id"], "score": 0.0, "text": r["text"], "snippet": r["text"][:200], "metadata": r["metadata"]})
        # Store query result in cache (text queries only)
        if _redis and not req.embedding and results:
            try:
                cache_key = _qkey(req.namespace or "global", req.q or "", req.top_k or 5)
                _redis.set(cache_key, json.dumps(results), ex=_QUERY_TTL)
            except Exception:
                pass
        return {"results": results}
    except Exception as e:
        log_exception("ECM5", e, extra={"request": req.dict()})
        raise HTTPException(status_code=500, detail="Query failed")


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: str):
    if SessionLocal:
        db = SessionLocal()
        try:
            mem = db.query(Memory).filter(Memory.id == str(memory_id)).first()
            if not mem:
                raise HTTPException(status_code=404, detail="Not found")
            db.delete(mem)
            db.commit()
            if _redis:
                try:
                    _redis.delete(f"memory:{memory_id}")
                except Exception:
                    pass
            return {"deleted": True, "id": str(memory_id)}
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            log_exception("ECM6", e, extra={"memory_id": memory_id})
            raise HTTPException(status_code=500, detail="Failed to delete memory")
        finally:
            db.close()
    else:
        rec = _STORE.pop(memory_id, None)
        if not rec:
            raise HTTPException(status_code=404, detail="Not found")
        return {"deleted": True, "id": memory_id}
