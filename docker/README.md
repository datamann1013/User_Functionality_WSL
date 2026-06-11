# RuneCore Docker Deployment

This directory contains the ecosystem-wide compose files.

| File | Purpose |
|------|---------|
| `docker-compose.unified.yml` | **Canonical** full-stack deployment. Service names, build contexts, isolated bridge networks, and healthchecks defined here are the source of truth. |
| `docker-compose.prod.yml` | Thin production variant of unified.yml: secrets are required (compose fails fast if unset) and mTLS is always enforced. Mirror unified.yml changes into it. |
| `.env.sample` | Template for `docker/.env` — required variables for both files above. |
| `dev-base/` | Shared dev base images. |

```bash
cp docker/.env.sample docker/.env        # fill in real secrets
docker compose -f docker/docker-compose.unified.yml --env-file docker/.env up -d
# or the production variant:
docker compose -f docker/docker-compose.prod.yml --env-file docker/.env up -d
```

Build contexts are relative to `docker/`, so modules resolve as `../projects/<Module>`
(e.g. `../projects/RuneCore_Core`, `../projects/RuneCore_AI`, `../projects/RuneCore_Memory`,
`../projects/RuneGuard_Logger`).

---

## 1. Dev workflow (per-module compose + external networks)

Day-to-day development does **not** use the files in this directory. Each module ships its
own `docker-compose.dev.yml` (e.g. `projects/RuneCore_Core/docker-compose.dev.yml`), and the
modules are joined through **pre-existing external Docker networks** that model the VLAN design:

| Network | Members |
|---------|---------|
| `runecore_dev` | Core, HA, Logger, Dashboard backend, Insight (shared backbone) |
| `runecore_ai_net` | Ollama, ollama_wrapper, AI backend, frontend |
| `runecore_memory_net` | PostgreSQL, Redis, InfluxDB, CoreMemory API |
| `runecore_dashboard_net` | Dashboard backend + frontend (reserved; the Dashboard dev compose currently attaches to `runecore_dev`) |

Because the dev compose files declare these networks as `external: true`, they must exist
**before** `docker compose up`, otherwise compose aborts:

```bash
docker network create runecore_dev
docker network create runecore_ai_net
docker network create runecore_memory_net
docker network create runecore_dashboard_net
```

The easier path is the orchestrated start script, which creates the networks and brings the
modules up in dependency order (Core → HA → Memory → Logger → Insight/Dashboard → AI):

```bash
./scripts/start_system.sh
```

Cross-VLAN traffic is routed through Core's internal HTTP proxy:
`http://runecore_core:11441/api/proxy/{ServiceName}/{path}`.

---

## 2. mTLS certificate bootstrap (unified.yml / prod.yml)

Core (`core_primary`) is the PKI root. On first boot it creates a CA inside its data volume:

- `/data/ca_cert.pem` — CA certificate
- `/data/ca_key.enc` — CA private key, encrypted with `CA_PASSPHRASE` (from `docker/.env`)

The Python services authenticate to Core over mTLS and expect **signed client certificates**
in the shared `runecore_certs` volume (mounted at `/certs`, read-only for everything except
`core_primary`):

```
/certs/ca.crt                  ← CA certificate (all services)
/certs/ai/client.crt|.key      ← AI backend        (ai_backend)
/certs/memory/client.crt|.key  ← CoreMemory API    (core_memory_api)
/certs/logger/client.crt|.key  ← RuneGuard Logger  (runeguard_logger)
```

These are **not** generated automatically — an operator must populate the volume once,
before the first full `docker compose up`. The CA signing code lives in
`projects/RuneCore_Core/src/ca.rs`, exposed two ways:

- CLI subcommand: `runecore_core sign-csr` (`projects/RuneCore_Core/src/cli.rs`)
- HTTP API: `POST /api/v1/pki/sign` with `{"csr_pem": "...", "role": "client", "days_valid": 365}`

### Bootstrap procedure

```bash
COMPOSE="docker compose -f docker/docker-compose.unified.yml --env-file docker/.env"

# 1. Start Core alone — first boot initialises the CA in the core data volume
$COMPOSE up -d core_primary
CORE=$($COMPOSE ps -q core_primary)

# 2. Generate a key + CSR for each service (repeat for ai, memory, logger)
for svc in ai memory logger; do
  openssl req -new -newkey rsa:2048 -nodes \
    -keyout "$svc-client.key" -out "$svc.csr" -subj "/CN=$svc"
done

# 3. Sign each CSR with Core's CA.
#    The CLI reads the passphrase from /data/ca_passphrase.txt — write it once from the env:
docker exec "$CORE" sh -c 'printf "%s" "$RUNECORE_CA_PASSPHRASE" > /data/ca_passphrase.txt'
for svc in ai memory logger; do
  docker cp "$svc.csr" "$CORE:/tmp/$svc.csr"
  docker exec "$CORE" /app/runecore_core sign-csr \
    --data-dir /data --csr-file "/tmp/$svc.csr" --role client \
    --days 365 --out "/tmp/$svc-client.crt"
  docker cp "$CORE:/tmp/$svc-client.crt" "$svc-client.crt"
done

# 4. Export the CA certificate
docker exec "$CORE" cat /data/ca_cert.pem > ca.crt

# 5. Populate the runecore_certs volume
docker run --rm -v runecore_certs:/certs -v "$PWD:/in:ro" alpine sh -c '
  set -e
  cp /in/ca.crt /certs/ca.crt
  for svc in ai memory logger; do
    mkdir -p "/certs/$svc"
    cp "/in/$svc-client.crt" "/certs/$svc/client.crt"
    cp "/in/$svc-client.key" "/certs/$svc/client.key"
    chmod 600 "/certs/$svc/client.key"
  done'

# 6. Bring up the rest of the stack
$COMPOSE up -d

# 7. Clean up local key material
rm -f ./*.csr ./*-client.crt ./*-client.key ./ca.crt
```

Alternative to step 3: once Core is up you can sign via the API instead of the CLI
(`role` defaults to `client`, `days_valid` defaults to 7 — pass 365 explicitly):

```bash
curl -sk https://localhost:11440/api/v1/pki/sign \
  -H "Content-Type: application/json" \
  -d "{\"csr_pem\": $(python -c 'import json,sys;print(json.dumps(open(sys.argv[1]).read()))' ai.csr), \"role\": \"client\", \"days_valid\": 365}"
```

(Note: with mTLS enforced this endpoint itself requires a client cert, so the
`docker exec` CLI path is the canonical first-time bootstrap. For local development you can
set `DISABLE_MTLS=true` in `docker/.env` — unified.yml only; prod.yml always enforces mTLS.)

### Renewal

Certificates signed with `--days 365` expire after a year. Re-run steps 2-5 with new CSRs,
then restart the affected services (`$COMPOSE restart ai_backend core_memory_api runeguard_logger`).
