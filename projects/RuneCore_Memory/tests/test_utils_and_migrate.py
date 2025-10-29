import os
import types


def test_log_error_remote_success(monkeypatch):
    # Import module under test
    import projects.RuneCore_Memory.core_memory.utils as utils

    class DummyResp:
        def __init__(self, status_code):
            self.status_code = status_code

    def fake_post(url, json=None, timeout=None):
        assert url == utils.ERRORLOGGER_URL
        assert 'error_code' in json
        return DummyResp(200)

    monkeypatch.setattr('projects.RuneCore_Memory.core_memory.utils.requests.post', fake_post)
    ok = utils.log_error_remote('X001', 'msg', extra={'a': 1})
    assert ok is True


def test_log_error_remote_failure(monkeypatch):
    import projects.RuneCore_Memory.core_memory.utils as utils

    def fake_post_raise(*a, **k):
        raise RuntimeError('no network')

    monkeypatch.setattr('projects.RuneCore_Memory.core_memory.utils.requests.post', fake_post_raise)
    ok = utils.log_error_remote('X002', 'msg')
    assert ok is False


def test_log_exception_calls_log_error_remote(monkeypatch):
    import projects.RuneCore_Memory.core_memory.utils as utils

    calls = {}

    def fake_log(code, message, extra=None, severity=None):
        calls['code'] = code
        calls['message'] = message
        return True

    monkeypatch.setattr('projects.RuneCore_Memory.core_memory.utils.log_error_remote', fake_log)

    try:
        raise ValueError('boom')
    except Exception as e:
        ok = utils.log_exception('E100', e, extra={'x': 1})
        assert ok is True
        assert calls['code'] == 'E100'


def test_run_migrations_calls_init_db(monkeypatch, tmp_path):
    import sys, os, types
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

    # Insert lightweight fake sqlalchemy package/module structure to avoid heavy dependencies
    import types as _types
    sqlalchemy_mod = _types.ModuleType('sqlalchemy')
    sqlalchemy_mod.create_engine = lambda *a, **k: _types.SimpleNamespace(connect=lambda: None)
    sqlalchemy_mod.Column = lambda *a, **k: None
    sqlalchemy_mod.String = lambda *a, **k: None
    sqlalchemy_mod.Text = lambda *a, **k: None
    sqlalchemy_mod.JSON = lambda *a, **k: None
    sqlalchemy_mod.DateTime = lambda *a, **k: None
    sqlalchemy_mod.Integer = lambda *a, **k: None
    sqlalchemy_mod.ForeignKey = lambda *a, **k: None
    sqlalchemy_mod.Float = lambda *a, **k: None
    sqlalchemy_mod.sessionmaker = lambda bind=None: (lambda: None)

    # ext.declarative
    ext_mod = _types.ModuleType('sqlalchemy.ext')
    decl_mod = _types.ModuleType('sqlalchemy.ext.declarative')
    def declarative_base():
        class Base:
            pass
        return Base
    decl_mod.declarative_base = declarative_base
    sys.modules['sqlalchemy'] = sqlalchemy_mod
    sys.modules['sqlalchemy.ext'] = ext_mod
    sys.modules['sqlalchemy.ext.declarative'] = decl_mod

    # dialects.postgresql stub
    pg_mod = _types.ModuleType('sqlalchemy.dialects.postgresql')
    pg_mod.UUID = lambda *a, **k: None
    pg_mod.JSONB = lambda *a, **k: None
    sys.modules['sqlalchemy.dialects.postgresql'] = pg_mod
    sys.modules['sqlalchemy.dialects'] = _types.ModuleType('sqlalchemy.dialects')
    # orm.sessionmaker
    orm_mod = _types.ModuleType('sqlalchemy.orm')
    orm_mod.sessionmaker = lambda bind=None: (lambda: None)
    sys.modules['sqlalchemy.orm'] = orm_mod

    # Provide fake core_memory.db module with init_db and engine to be imported inside run_migrations
    core_db_mod = types.ModuleType('core_memory.db')
    def fake_init_db():
        core_db_mod.called = True
    core_db_mod.init_db = fake_init_db
    # provide a dummy engine with connect method to satisfy top-level imports
    core_db_mod.engine = types.SimpleNamespace(connect=lambda: None)
    sys.modules['core_memory.db'] = core_db_mod

    monkeypatch.delenv('PGVECTOR_ENABLED', raising=False)
    import projects.RuneCore_Memory.core_memory.migrate as migrate
    migrate.run_migrations()
    assert getattr(core_db_mod, 'called', False) is True


def test_run_migrations_with_pgvector(monkeypatch):
    import sys, os, types
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

    # Provide fake sqlalchemy modules as above
    fake_sqlalchemy = types.SimpleNamespace()
    fake_sqlalchemy.create_engine = lambda *a, **k: types.SimpleNamespace(connect=lambda: None)
    fake_sqlalchemy.Column = lambda *a, **k: None
    fake_sqlalchemy.String = lambda *a, **k: None
    fake_sqlalchemy.Text = lambda *a, **k: None
    fake_sqlalchemy.JSON = lambda *a, **k: None
    fake_sqlalchemy.DateTime = lambda *a, **k: None
    fake_sqlalchemy.Integer = lambda *a, **k: None
    fake_sqlalchemy.ForeignKey = lambda *a, **k: None
    fake_sqlalchemy.Float = lambda *a, **k: None
    fake_sqlalchemy.declarative_base = lambda: type('Base', (object,), {})
    fake_sqlalchemy.sessionmaker = lambda bind=None: (lambda: None)
    sys.modules['sqlalchemy'] = fake_sqlalchemy
    postgresql = types.SimpleNamespace(UUID=lambda *a, **k: None, JSONB=lambda *a, **k: None)
    dialects = types.SimpleNamespace(postgresql=postgresql)
    sys.modules['sqlalchemy.dialects'] = dialects
    sys.modules['sqlalchemy.dialects.postgresql'] = postgresql
    # orm.sessionmaker
    orm_mod = types.ModuleType('sqlalchemy.orm')
    orm_mod.sessionmaker = lambda bind=None: (lambda: None)
    sys.modules['sqlalchemy.orm'] = orm_mod

    # Provide fake core_memory.db module with init_db to be imported inside run_migrations
    core_db_mod = types.ModuleType('core_memory.db')
    core_db_mod.init_db = lambda: None
    # engine will be replaced by db_pkg below; still provide placeholder
    core_db_mod.engine = types.SimpleNamespace(connect=lambda: None)
    sys.modules['core_memory.db'] = core_db_mod

    # fake engine that exposes connect() returning object with execute and commit
    class DummyConn:
        def execute(self, sql):
            assert 'CREATE EXTENSION' in sql

        def commit(self):
            pass

    class DummyEngine:
        def connect(self):
            return DummyConn()

    monkeypatch.setenv('PGVECTOR_ENABLED', '1')
    # Ensure migrate imports will use our Fake engine by placing it into core_memory.db as well
    # The migrate module imports engine from core_memory.db at top-level, so patch sys.modules before import
    db_pkg = types.ModuleType('core_memory')
    db_pkg.db = types.ModuleType('core_memory.db')
    db_pkg.db.engine = DummyEngine()
    db_pkg.db.init_db = lambda: None
    sys.modules['core_memory'] = db_pkg
    sys.modules['core_memory.db'] = db_pkg.db

    import projects.RuneCore_Memory.core_memory.migrate as migrate
    migrate.run_migrations()
