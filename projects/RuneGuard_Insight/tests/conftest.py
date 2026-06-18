"""
Test bootstrap for RuneGuard_Insight.

insight.py imports `docker`, `requests`, and the shared `CoreClient`. To keep
the smoke tests dependency-light and hermetic we:
  - inject a stub `docker` module (so the real Docker SDK/daemon isn't needed),
  - put the module dir + repo `projects/` dir on sys.path so `insight` and
    `shared_utils.core_client` import cleanly,
  - expose the imported insight module as a fixture.
"""
import os
import sys
import types

import pytest

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECTS_DIR = os.path.dirname(MODULE_DIR)

for p in (MODULE_DIR, PROJECTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)


def _install_docker_stub():
    """Install a minimal `docker` stub if the real SDK is absent."""
    if "docker" in sys.modules:
        return
    try:
        import docker  # noqa: F401
        return
    except Exception:
        pass

    stub = types.ModuleType("docker")

    def from_env(*args, **kwargs):  # overridden per-test via monkeypatch
        raise RuntimeError("docker stub: from_env not configured")

    stub.from_env = from_env
    errors = types.ModuleType("docker.errors")

    class DockerException(Exception):
        pass

    errors.DockerException = DockerException
    stub.errors = errors
    sys.modules["docker"] = stub
    sys.modules["docker.errors"] = errors


_install_docker_stub()


@pytest.fixture
def insight(monkeypatch):
    # Keep ports off well-known values during tests.
    monkeypatch.setenv("HEALTH_PORT", "0")
    import importlib
    mod = importlib.import_module("insight")
    importlib.reload(mod)
    return mod
