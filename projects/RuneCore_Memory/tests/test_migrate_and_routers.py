import os
import sys
import types
import pytest


def test_run_migrations_handles_pgvector_exception(monkeypatch):
    # Prepare a fake core_memory.db module with init_db and engine.connect raising
    fake_db = types.SimpleNamespace()

    def fake_init_db():
        return None

    class BadConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, *a, **k):
            raise RuntimeError("unable to create extension")

    class FakeEngine:
        def connect(self):
            return BadConn()

    fake_db.init_db = fake_init_db
    fake_db.engine = FakeEngine()

    # Inject into sys.modules before importing migrate
    sys.modules["core_memory.db"] = fake_db

    # Enable PGVECTOR
    monkeypatch.setenv("PGVECTOR_ENABLED", "1")

    # Import migrate and run
    import importlib
    migrate = importlib.import_module("projects.RuneCore_Memory.core_memory.migrate")
    importlib.reload(migrate)

    # Should not raise despite engine.execute raising
    migrate.run_migrations()


def test_create_get_query_store_paths(monkeypatch):
    # Import the memories router module
    import importlib
    mod = importlib.import_module("projects.RuneCore_Memory.core_memory.routers.memories")
    importlib.reload(mod)

    # Ensure SessionLocal is falsy so code uses in-memory _STORE
    mod.SessionLocal = None
    mod._STORE.clear()

    # Create a memory via the create_memory handler using a simple payload object
    class FakePayload:
        def __init__(self, text, namespace, agent_id=None, metadata=None):
            self.text = text
            self.namespace = namespace
            self.agent_id = agent_id
            self.metadata = metadata or {}

        def dict(self):
            return {"text": self.text, "namespace": self.namespace, "agent_id": self.agent_id, "metadata": self.metadata}

    payload = FakePayload(text="hello world", namespace="testspace")
    res = mod.create_memory(payload)
    assert isinstance(res, dict)
    mid = res.get("id")
    assert mid in mod._STORE
    assert mod._STORE[mid]["text"] == "hello world"

    # get_memory should return the same record
    got = mod.get_memory(mid)
    assert got["id"] == mid
    assert got["text"] == "hello world"

    # query_memories should return this memory when namespace matches
    qr = mod.query_memories(mod.QueryRequest(q=None, embedding=None, namespace="testspace", top_k=5))
    assert "results" in qr
    assert any(r["id"] == mid for r in qr["results"]) is True


def test_get_memory_not_found_raises(monkeypatch):
    import importlib
    mod = importlib.import_module("projects.RuneCore_Memory.core_memory.routers.memories")
    mod.SessionLocal = None
    mod._STORE.clear()

    with pytest.raises(Exception) as exc:
        mod.get_memory("nonexistent-id")
    # Fast check for HTTPException-like behavior
    assert "Memory not found" in str(exc.value)
