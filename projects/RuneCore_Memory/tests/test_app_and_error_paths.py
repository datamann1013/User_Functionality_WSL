import os
import sys
import importlib
from types import SimpleNamespace
from datetime import datetime
import uuid

import pytest

# ensure project path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import asyncio

# shim fastapi for import-time in tests
if 'fastapi' not in sys.modules:
    import types as _types
    class _HTTPException(Exception):
        def __init__(self, status_code=None, detail=None):
            super().__init__(detail)

    class _FakeRouter:
        def post(self, *a, **k):
            def _dec(f):
                return f
            return _dec

        def get(self, *a, **k):
            def _dec(f):
                return f
            return _dec

        def exception_handler(self, *a, **k):
            def _dec(f):
                return f
            return _dec

    class _FakeFastAPI:
        def __init__(self, *a, **k):
            self._routes = {}

        def add_middleware(self, *a, **k):
            return

        def include_router(self, *a, **k):
            return

        def get(self, *a, **k):
            def _dec(f):
                return f
            return _dec
        def exception_handler(self, *a, **k):
            def _dec(f):
                return f
            return _dec

    sys.modules['fastapi'] = _types.SimpleNamespace(FastAPI=lambda *a, **k: _FakeFastAPI(), HTTPException=_HTTPException, APIRouter=lambda *a, **k: _FakeRouter())
    # middleware subpackage
    sys.modules['fastapi.middleware'] = _types.SimpleNamespace()
    sys.modules['fastapi.middleware.cors'] = _types.SimpleNamespace(CORSMiddleware=lambda *a, **k: None)
    # requests and responses
    sys.modules['fastapi.requests'] = _types.SimpleNamespace(Request=SimpleNamespace)
    sys.modules['fastapi.responses'] = _types.SimpleNamespace(JSONResponse=lambda status_code=500, content=None: SimpleNamespace(body=(str(content) if content else b""), media=content))
    # shim pydantic
    class _FakeModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    sys.modules['pydantic'] = _types.SimpleNamespace(BaseModel=_FakeModel, Field=lambda **k: None)
    # shim sqlalchemy minimal symbols
    sys.modules['sqlalchemy'] = _types.SimpleNamespace(create_engine=lambda *a, **k: None, Column=lambda *a, **k: None, String=str, Text=str, JSON=dict, DateTime=datetime, Integer=int, ForeignKey=lambda *a, **k: None, Float=float)
    sys.modules['sqlalchemy.dialects.postgresql'] = _types.SimpleNamespace(UUID=lambda *a, **k: str, JSONB=dict)
    sys.modules['sqlalchemy.ext.declarative'] = _types.SimpleNamespace(declarative_base=lambda: object)
    sys.modules['sqlalchemy.orm'] = _types.SimpleNamespace(sessionmaker=lambda **k: None)
    # shim numpy minimal API
    import math as _math
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
    sys.modules['numpy'] = _types.SimpleNamespace(array=lambda x, dtype=None: _FakeND(x), pad=lambda a, pad, constant_values=0.0: _FakeND(list(a) + [constant_values]*pad[1]), dot=lambda x,y: sum(float(xi)*float(yi) for xi,yi in zip(x,y)), linalg=_types.SimpleNamespace(norm=lambda v: _math.sqrt(sum(float(xi)**2 for xi in v))))

import core_memory.app as app_module
from core_memory.routers import memories


def test_health_endpoint():
    h = app_module.health()
    assert isinstance(h, dict)
    assert h.get("status") == "ok"


def test_global_exception_handler_returns_json():
    # create a fake request with a url attribute
    fake_req = SimpleNamespace(url="/test/path")
    # call the async handler
    res = asyncio.run(app_module.global_exception_handler(fake_req, Exception("boom")))
    assert hasattr(res, 'body') or hasattr(res, 'media')
    content = None
    try:
        # starlette JSONResponse may have .body
        content = res.body.decode('utf-8')
    except Exception:
        try:
            content = res.media
        except Exception:
            content = None
    assert content is not None


def test_create_memory_commit_failure_raises(monkeypatch):
    # simulate SessionLocal where commit fails
    class FailSession:
        def __init__(self):
            self._added = []

        def add(self, obj):
            self._added.append(obj)

        def commit(self):
            raise Exception("commit failed")

        def rollback(self):
            return

        def refresh(self, obj):
            return

        def close(self):
            return

    monkeypatch.setattr(memories, 'SessionLocal', lambda: FailSession())

    # Simple payload with dict
    class Payload:
        namespace = "global"
        agent_id = None
        text = "x"
        metadata = {}
        def dict(self):
            return {"text": self.text}

    # ensure Memory/Embedding classes are simple
    class SimpleModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k if k != 'metadata' else 'metadata_json', v)
            self.id = None
            self.created_at = None
        id = None
        namespace = None

    monkeypatch.setattr(memories, 'Memory', SimpleModel)
    monkeypatch.setattr(memories, 'Embedding', SimpleModel)

    with pytest.raises(Exception):
        memories.create_memory(Payload())


def test_create_memory_embedding_failure_returns(monkeypatch):
    # first commit ok, second commit (embedding) fails
    class TwoCommitSession:
        def __init__(self):
            self._added = []
            self._commits = 0

        def add(self, obj):
            self._added.append(obj)

        def commit(self):
            if self._commits == 0:
                # emulate successful first commit and set id on objects
                for obj in self._added:
                    if not getattr(obj, 'id', None):
                        obj.id = uuid.uuid4()
                    if not getattr(obj, 'created_at', None):
                        obj.created_at = datetime.utcnow()
                self._added = []
                self._commits += 1
            else:
                self._commits += 1
                raise Exception("embedding commit failed")

        def refresh(self, obj):
            return

        def rollback(self):
            self._added = []

        def close(self):
            return

        def query(self, model):
            return SimpleQuery({})

    class SimpleQuery:
        def __init__(self, store):
            self._store = store

        def all(self):
            return []

    monkeypatch.setattr(memories, 'SessionLocal', lambda: TwoCommitSession())

    class Payload:
        namespace = "global"
        agent_id = None
        text = "x"
        metadata = {}
        def dict(self):
            return {"text": self.text}

    class SimpleModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k if k != 'metadata' else 'metadata_json', v)
            self.id = None
            self.created_at = None
        id = None
        namespace = None

    monkeypatch.setattr(memories, 'Memory', SimpleModel)
    monkeypatch.setattr(memories, 'Embedding', SimpleModel)

    res = memories.create_memory(Payload())
    assert res["text"] == "x"
