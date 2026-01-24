# GitHub Copilot Instructions for RuneCore Ecosystem

## 🎯 Project Context
The RuneCore Ecosystem is a comprehensive AI service platform with security-first development practices, enterprise-grade CI/CD pipeline, and distributed architecture.

<!-- Copilot / AI agent guidance: focused, actionable notes for contributors and coding agents -->

# RuneCore Ecosystem — Quick AI-Agent Guide

Purpose: give AI coding agents the minimal, concrete knowledge to be productive in this repo.

- **Big picture**: repository hosts multiple containerized microservices.
	- `projects/RuneCore_AI/` — AI service (backend, frontend, `ollama_service/`). Default dev files: `docker-compose.dev.yml`, `start_redis_dev.sh`, `README.md`.
	- `projects/RuneCore_Core/` — Rust-based core (see `Cargo.toml`, `src/`).
	- `projects/RuneCore_Memory/` — DB + migrations (`alembic.ini`, `manage_migrations.sh`, `migrate.py`, `env.sample`).
	- `projects/RuneGuard_Logger/` — centralized logger (`error_logger_service.py`, `logger.py`, tests `test_*`). Services register with this logger.
	- `projects/hidden_toolbar/` — desktop helper (`launcher.py`, `detect_fullscreen.sh`).

- **How services integrate**:
	- Services communicate via HTTP REST and register with core components — see `test_register_with_core.py` / `test_register_with_core_memory.py` in multiple projects for examples.
	- Centralized logging is handled by `RuneGuard_Logger`; keep logs structured JSON.

- **Concrete run / dev commands** (examples):
	- Start full dev stack (Linux/macOS): `./scripts/start_all_with_compose.sh` (uses per-project `docker-compose.dev.yml`).
	- Stop full stack: `./scripts/stop_all_with_compose.sh`.
	- Build dev base images: `./scripts/build_dev_bases.sh`.
	- Start AI service locally (Windows helper exists): `.\start_ai_service.bat` (or run compose in WSL/ bash).
	- Run migrations: `cd projects/RuneCore_Memory && ./manage_migrations.sh` or `python migrate.py`.
	- Run tests for a project: `pytest projects/RuneGuard_Logger -q`.

- **Important ports & env vars** (search and prefer env vars):
	- AI Service: default `5000` (override with `PORT` env var). See `start_ai_service.bat` and `projects/RuneCore_AI/README.md`.
	- ErrorLogger: default `5001` (override with `ERRORLOGGER_PORT`). See `projects/RuneGuard_Logger/error_logger_service.py`.
	- JWT secret / DB URLs / other credentials must come from env vars; do not hardcode.

- **Project-specific conventions and patterns**
	- No bare `except:` — all handlers must catch specific exceptions (many Python files and tests follow this pattern).
	- Use environment variables for ports, secrets, database URLs; reflect changes in `env.sample` under `projects/RuneCore_Memory`.
	- Docker images: avoid `../` in `COPY` lines; use build context-root paths (see `docker/` and per-project `Dockerfile`s).
	- Tests include registration/integration patterns: use `test_register_with_core*.py` examples when adding new services.

- **Where to look for examples / entry points**
	- Start scripts: root `start_ai_service.bat`, `start_errorlogger.sh` (in `RuneGuard_Logger`), `scripts/` helpers.
	- Docker and compose: `docker/docker-compose.prod.yml`, per-project `docker-compose.dev.yml` files.
	- Migrations: `projects/RuneCore_Memory/manage_migrations.sh`, `alembic/` folder.
	- Logging: `projects/RuneGuard_Logger/logger.py` and `error_logger_service.py` for structured JSON format.

- **When editing code**
	- Run related unit tests for the changed project directory (e.g., `pytest projects/RuneCore_Memory -q`).
	- Update `env.sample`, README, and any per-project `docker-compose` if adding new env vars or ports.
	- Preserve API contracts used by `test_register_with_core*.py` tests and error logger schema.

If anything important is missing or unclear (service entrypoint, port, migration step), tell me which component to inspect and I’ll expand the relevant section.  

<!-- End of file -->
```
- [ ] Authentication and authorization implemented
