import os
import sys
from datetime import datetime

import pytest
import types
import sys

# ensure project package importability
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# fastapi may not be installed in the test env; inject a minimal fake module
if 'fastapi' not in sys.modules:
    class _FakeRouter:
        def post(self, *a, **k):
            def _dec(f):
                return f
            return _dec

        def get(self, *a, **k):
            def _dec(f):
                return f
            return _dec

    fake_fastapi = types.SimpleNamespace(APIRouter=lambda *a, **k: _FakeRouter(), HTTPException=Exception)
    sys.modules['fastapi'] = fake_fastapi

# shim pydantic
if 'pydantic' not in sys.modules:
    class _FakeModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    fake_pydantic = types.SimpleNamespace(BaseModel=_FakeModel, Field=lambda **k: None)
    sys.modules['pydantic'] = fake_pydantic

# shim numpy used for vector math
if 'numpy' not in sys.modules:
    import math

    class _FakeND:
        def __init__(self, arr):
            self._arr = list(arr)

        def __array__(self):
            return self._arr

        def __len__(self):
            return len(self._arr)

        def __getitem__(self, i):
            if isinstance(i, slice):
                return _FakeND(self._arr[i])
            return float(self._arr[i])

        def __iter__(self):
            return iter(self._arr)

    fake_numpy = types.SimpleNamespace(array=lambda x, dtype=None: _FakeND(x), pad=lambda a, pad, constant_values=0.0: _FakeND(list(a) + [constant_values]*pad[1]), dot=lambda x,y: sum(float(xi)*float(yi) for xi,yi in zip(x,y)), linalg=types.SimpleNamespace(norm=lambda v: math.sqrt(sum(float(xi)**2 for xi in v))))
    sys.modules['numpy'] = fake_numpy

# shim redis to avoid import error; router handles missing redis gracefully
if 'redis' not in sys.modules:
    sys.modules['redis'] = types.SimpleNamespace(from_url=lambda u: None)

# shim sqlalchemy since we don't want to install it for unit tests; create minimal symbols
if 'sqlalchemy' not in sys.modules:
    class _Col:
        def __init__(self, *a, **k):
            pass

    fake_sqlalchemy = types.SimpleNamespace(create_engine=lambda *a, **k: None, Column=_Col, String=str, Text=str, JSON=dict, DateTime=datetime, Integer=int, ForeignKey=lambda *a, **k: None, Float=float)
    sys.modules['sqlalchemy'] = fake_sqlalchemy

    # subpackages
    sys.modules['sqlalchemy.dialects'] = types.SimpleNamespace(postgresql=types.SimpleNamespace(UUID=lambda *a, **k: str, JSONB=dict))
    # create package-like entries for nested imports
    sys.modules['sqlalchemy.dialects.postgresql'] = types.SimpleNamespace(UUID=lambda *a, **k: str, JSONB=dict)
    sys.modules['sqlalchemy.ext'] = types.SimpleNamespace(declarative=types.SimpleNamespace(declarative_base=lambda: object))
    sys.modules['sqlalchemy.ext.declarative'] = types.SimpleNamespace(declarative_base=lambda: object)
    sys.modules['sqlalchemy.orm'] = types.SimpleNamespace(sessionmaker=lambda **k: None)

from core_memory.routers import memories


def test__text_to_vector_length_and_determinism():
    a = memories._text_to_vector("hello world", dim=16)
    b = memories._text_to_vector("hello world", dim=16)
    assert len(list(a)) == 16
    assert list(a) == list(b)


def test_create_and_get_memory_in_memory_store(monkeypatch):
    # force SessionLocal to None to exercise in-memory fallback
    monkeypatch.setattr(memories, 'SessionLocal', None)
    # clear store
    memories._STORE.clear()

    class Payload:
        namespace = "global"
        agent_id = "agent-1"
        text = "this is a test memory"
        metadata = {"k": "v"}

    payload = Payload()
    res = memories.create_memory(payload)
    assert res["text"] == payload.text
    assert res["namespace"] == "global"
    mid = res["id"]

    got = memories.get_memory(mid)
    assert got["id"] == mid
    assert got["text"] == payload.text


def test_get_memory_not_found_raises(monkeypatch):
    monkeypatch.setattr(memories, 'SessionLocal', None)
    memories._STORE.clear()
    with pytest.raises(Exception):
        memories.get_memory("non-existent-id")


def test_query_memories_in_memory_store(monkeypatch):
    monkeypatch.setattr(memories, 'SessionLocal', None)
    memories._STORE.clear()
    # insert two records
    p1 = type('P', (), {"namespace": "global", "agent_id": None, "text": "first memory", "metadata": {}})()
    p2 = type('P', (), {"namespace": "other", "agent_id": None, "text": "second memory", "metadata": {}})()
    r1 = memories.create_memory(p1)
    r2 = memories.create_memory(p2)

    class Q:
        q = None
        embedding = None
        namespace = "global"
        top_k = 5

    q = Q()
    out = memories.query_memories(q)
    assert isinstance(out, dict)
    assert "results" in out
    assert any(r["id"] == r1["id"] for r in out["results"])
