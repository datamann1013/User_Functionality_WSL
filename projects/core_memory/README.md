# CoreMemory Microservice

Minimal scaffold for the CoreMemory microservice. Provides a simple FastAPI app and in-memory store to iterate on.

Config via environment variables (see `env.sample`).

Endpoints:
- GET /v1/health
- POST /v1/memories
- GET /v1/memories/{id}

This is an initial scaffold. Integrations (Postgres, Redis, InfluxDB, backups, auth) will be added iteratively.
