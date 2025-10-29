import os
import subprocess
import time
import requests

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
COMPOSE_FILE = os.path.join(BASE_DIR, 'docker-compose.dev.yml')
CORE_URL = 'http://localhost:5010'


def run(cmd, cwd=None, timeout=60):
    return subprocess.run(cmd, shell=True, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)


def wait_for_health(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url + '/v1/health', timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError('Service did not become healthy')


import pytest


@pytest.mark.skip(reason="Integration test requiring docker-compose; run manually")
def test_create_get_query_flow():
    # Start compose stack
    run(f'docker-compose -f {COMPOSE_FILE} up --build -d', cwd=BASE_DIR)

    # Run migrations in the core container using manage_migrations.sh
    env = os.environ.copy()
    env['POSTGRES_DSN'] = env.get('POSTGRES_DSN', 'postgresql://core:core@localhost:15432/corememory')
    run(f'docker-compose -f {COMPOSE_FILE} exec -T core_memory python /app/migrate.py', cwd=BASE_DIR)

    # Wait for health
    wait_for_health(CORE_URL, timeout=30)

    # Create memory
    payload = {"text": "hello world", "namespace": "test"}
    r = requests.post(CORE_URL + '/v1/memories', json=payload, timeout=5)
    assert r.status_code == 200
    mid = r.json()['id']

    # Get memory
    r2 = requests.get(CORE_URL + f'/v1/memories/{mid}', timeout=5)
    assert r2.status_code == 200
    assert 'hello world' in r2.json().get('text', '')

    # Query (simple)
    r3 = requests.post(CORE_URL + '/v1/memories/query', json={"q": "hello", "namespace": "test"}, timeout=5)
    assert r3.status_code == 200
    assert len(r3.json().get('results', [])) >= 1

    # Tear down
    run(f'docker-compose -f {COMPOSE_FILE} down -v', cwd=BASE_DIR)
