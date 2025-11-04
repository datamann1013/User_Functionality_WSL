import os
import sys
import uuid
from types import SimpleNamespace

import pytest

# ensure project path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core_memory.routers import memories


class FakeEmbeddingObj:
    def __init__(self, memory_id, vector):
        self.memory_id = memory_id
        self.vector = vector


class FakeMemoryObj:
    def __init__(self, id, text):
        self.id = id
        self.text = text
        self.metadata_json = {}


class FakeQuery:
    def __init__(self, embs, mems):
        self._embs = embs
        self._mems = mems

    def all(self):
        return self._embs

    def filter(self, *a, **k):
        return self

    def limit(self, n):
        return self

    def first(self):
        # return first memory
        vals = list(self._mems.values())
        return vals[0] if vals else None


class FakeSession:
    def __init__(self, embs, mems):
        self.embs = embs
        self.mems = mems

    def query(self, model):
        if model == memories.Embedding:
            return FakeQuery(self.embs, self.mems)
        if model == memories.Memory:
            return FakeQuery(self.embs, self.mems)


def test_vector_query_similarity(monkeypatch):
    # prepare embeddings and memories
    mid1 = str(uuid.uuid4())
    mid2 = str(uuid.uuid4())
    mems = {mid1: FakeMemoryObj(mid1, 'hello'), mid2: FakeMemoryObj(mid2, 'world')}
    # simple vectors (two dims)
    embs = [FakeEmbeddingObj(mid1, [1.0, 0.0]), FakeEmbeddingObj(mid2, [0.0, 1.0])]

    monkeypatch.setattr(memories, 'SessionLocal', lambda: FakeSession(embs, mems))

    class Q:
        q = None
        embedding = [1.0, 0.0]
        namespace = 'global'
        top_k = 2

    out = memories.query_memories(Q())
    assert 'results' in out
    # Expect the top result to be mid1 due to identical vector
    assert out['results'][0]['id'] == mid1
