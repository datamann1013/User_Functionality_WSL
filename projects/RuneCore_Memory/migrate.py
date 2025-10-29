import os
from core_memory.db import engine

PGVECTOR_ENABLED = os.environ.get("PGVECTOR_ENABLED", "false").lower() in ("1", "true", "yes")


def run_migrations():
    from core_memory.db import init_db
    init_db()
    if PGVECTOR_ENABLED:
        try:
            with engine.connect() as conn:
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
        except Exception:
            pass


if __name__ == '__main__':
    run_migrations()
    print("Migrations applied (scaffold)")
import os
from core_memory.db import engine

PGVECTOR_ENABLED = os.environ.get("PGVECTOR_ENABLED", "false").lower() in ("1", "true", "yes")


def run_migrations():
    # For scaffold: create tables
    from core_memory.db import init_db
    init_db()

    # Attempt to enable pgvector extension if requested
    if PGVECTOR_ENABLED:
        try:
            with engine.connect() as conn:
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
        except Exception:
            pass


if __name__ == '__main__':
    run_migrations()
    print("Migrations applied (scaffold)")
