import sys
import os
import types

import pytest

# ensure project path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from core_memory.routers import memories
except Exception:
    # lightweight shims for import-time dependencies
    import math as _math

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

    sys.modules['fastapi'] = types.SimpleNamespace(APIRouter=lambda *a, **k: _FakeRouter(), HTTPException=_HTTPException)
    sys.modules['pydantic'] = types.SimpleNamespace(BaseModel=lambda **k: None, Field=lambda **k: None)
    sys.modules['redis'] = types.SimpleNamespace(from_url=lambda u: None)
    # minimal numpy
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
    sys.modules['numpy'] = types.SimpleNamespace(array=lambda x, dtype=None: _FakeND(x), dot=lambda x,y: sum(float(xi)*float(yi) for xi,yi in zip(x,y)), linalg=types.SimpleNamespace(norm=lambda v: _math.sqrt(sum(float(xi)**2 for xi in v))))
    # minimal sqlalchemy
    sys.modules['sqlalchemy'] = types.SimpleNamespace(create_engine=lambda *a, **k: None, Column=lambda *a, **k: None, String=str, Text=str, JSON=dict, DateTime=object, Integer=int, ForeignKey=lambda *a, **k: None, Float=float)
    sys.modules['sqlalchemy.dialects.postgresql'] = types.SimpleNamespace(UUID=lambda *a, **k: str, JSONB=dict)
    sys.modules['sqlalchemy.ext.declarative'] = types.SimpleNamespace(declarative_base=lambda: object)
    sys.modules['sqlalchemy.orm'] = types.SimpleNamespace(sessionmaker=lambda **k: None)

    from core_memory.routers import memories


def test_get_memory_redis_cache(monkeypatch):
    # simulate redis cache hit
    monkeypatch.setattr(memories, '_redis', types.SimpleNamespace(get=lambda k: b'cached-text'))
    res = memories.get_memory('any-id')
    assert res['text'] == 'cached-text'


def test_query_vector_raises_on_embedding_error(monkeypatch):
    # simulate SessionLocal where querying embeddings raises
    class FailSession:
        def query(self, model):
            if model == memories.Embedding:
                raise Exception('db error')
            return types.SimpleNamespace(all=lambda: [])

    monkeypatch.setattr(memories, 'SessionLocal', lambda: FailSession())

    class Q:
        q = None
        embedding = [1.0, 0.0]
        namespace = 'global'
        top_k = 5
        def dict(self):
            return {'q': self.q, 'embedding': self.embedding, 'namespace': self.namespace, 'top_k': self.top_k}

    with pytest.raises(Exception):
        memories.query_memories(Q())
