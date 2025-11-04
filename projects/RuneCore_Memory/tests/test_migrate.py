import os
import importlib
import types
import sys

import pytest


def test_run_migrations_without_pgvector(monkeypatch, capsys):
    # ensure PGVECTOR disabled
    monkeypatch.delenv('PGVECTOR_ENABLED', raising=False)

    called = {}

    def fake_init_db():
        called['init_db'] = True

    # inject fake core_memory.db.init_db
    monkeypatch.setitem(sys.modules, 'core_memory.db', types.SimpleNamespace(init_db=fake_init_db, engine=None))

    # reload module under test
    migrate = importlib.reload(importlib.import_module('core_memory.migrate'))
    migrate.run_migrations()
    assert called.get('init_db')


def test_run_migrations_with_pgvector(monkeypatch):
    monkeypatch.setenv('PGVECTOR_ENABLED', '1')

    events = []

    class FakeConn:
        def execute(self, sql):
            events.append(('exec', sql))

        def commit(self):
            events.append(('commit', True))
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def connect(self):
            return FakeConn()

    def fake_init_db():
        events.append(('init', True))

    # inject fake core_memory.db so init_db and engine exist for import
    monkeypatch.setitem(sys.modules, 'core_memory.db', types.SimpleNamespace(init_db=fake_init_db, engine=FakeEngine()))

    migrate = importlib.reload(importlib.import_module('core_memory.migrate'))
    # force PGVECTOR enabled at runtime and attach FakeEngine to module
    migrate.PGVECTOR_ENABLED = True
    migrate.engine = FakeEngine()
    migrate.run_migrations()
    # expect init_db called and extension exec attempted
    assert ('init', True) in events
    assert any(e[0] == 'exec' for e in events)
