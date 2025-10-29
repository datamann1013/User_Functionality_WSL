# RuneCore Core — Alpha quickstart

This directory contains the RuneCore Core service (CA, service registry, PKI helpers). The project is "Docker-first": you can build, initialize, sign CSRs, and run the server using the provided Docker image and CLI helpers.

This README is a compact quickstart for the alpha. See the repository README for more context.

Prerequisites
- Docker installed and running (on Windows use WSL2 or Docker Desktop)
- Bash (WSL, Git Bash, or Linux/macOS shell)

Quickstart (Docker-first)

1) Build the image

```bash
docker build -t runecore-core:dev -f projects/core/Dockerfile projects/core
```

2) Initialize core data (creates CA, encrypted keys and server cert)

```bash
mkdir -p projects/core/data
docker run --rm -v "${PWD}/projects/core/data:/data" runecore-core:dev init-core --data-dir /data
```

3) Generate a client key and CSR (in a container)

```bash
docker run --rm -v "${PWD}/projects/core/data:/data" debian:bookworm-slim bash -lc \
  "apt-get update && apt-get install -y --no-install-recommends openssl && \
   openssl genrsa -out /data/client_key.pem 2048 && \
   openssl req -new -key /data/client_key.pem -subj '/CN=test-client' -out /data/client.csr"
```

4) Sign the CSR using the in-image CLI (role-aware EKU)

```bash
docker run --rm -v "${PWD}/projects/core/data:/data" runecore-core:dev sign-csr --data-dir /data --csr-file /data/client.csr --out /data/client_cert.pem --role client
```

5) Combine key+cert and run the server

```bash
cat projects/core/data/client_key.pem projects/core/data/client_cert.pem > projects/core/data/client_combined.pem
PASS=$(cat projects/core/data/ca_passphrase.txt)
docker run -d --name runecore-server -v "${PWD}/projects/core/data:/data" -p 11440:11440 \
  -e RUNECORE_DATA_DIR=/data -e RUNECORE_CA_PASSPHRASE="$PASS" runecore-core:dev
```

6) Health check (mTLS)

```bash
docker run --rm --network container:runecore-server -v "${PWD}/projects/core/data:/data" curlimages/curl:8.3.0 \
  sh -c "curl --cacert /data/ca_cert.pem --cert /data/client_combined.pem --resolve runecore.local:11440:127.0.0.1 https://runecore.local:11440/health"
```

7) Register a service (example POST)

Create `projects/core/data/payload.json` with a JSON body such as:

# RuneCore Core — Alpha quickstart

This folder contains the RuneCore Core service: a Docker-first Rust service that provides a simple CA/PKI for service bootstrapping, a service registry API, and CLI helpers for common ops.

This quickstart focuses on getting a runnable local environment for alpha testing: build, initialize the CA, create and sign client CSRs, run the server with mTLS enabled, and exercise the register endpoint.

Prerequisites
- Docker (Desktop/Engine) and a Bash shell (WSL, Git Bash, or Linux/macOS shell).

Quickstart (single-flow)

1) Build the image

```bash
docker build -t runecore-core:dev -f projects/core/Dockerfile projects/core
```

2) Prepare a writable data directory and initialize the core (CA, encrypted keys, server cert)

```bash
mkdir -p projects/core/data
docker run --rm -v "${PWD}/projects/core/data:/data" runecore-core:dev init-core --data-dir /data
```

The command writes the CA certificate (`/data/ca_cert.pem`), an encrypted CA private key (`/data/ca_key.enc`), the server cert (`/data/server_cert.pem`) and server key (`/data/server_key.enc`), and a passphrase file `/data/ca_passphrase.txt`.

3) Create a client key and CSR

```bash
docker run --rm -v "${PWD}/projects/core/data:/data" debian:bookworm-slim bash -lc \
  "apt-get update >/dev/null && apt-get install -y --no-install-recommends openssl >/dev/null && \
   openssl genrsa -out /data/client_key.pem 2048 && \
   openssl req -new -key /data/client_key.pem -subj '/CN=test-client' -out /data/client.csr"
```

4) Sign the CSR with the built-in CLI (creates a cert with proper EKU for the chosen role)

```bash
docker run --rm -v "${PWD}/projects/core/data:/data" runecore-core:dev sign-csr --data-dir /data --csr-file /data/client.csr --out /data/client_cert.pem --role client
```

5) Combine key+cert and start the server (mTLS enforced)

```bash
cat projects/core/data/client_key.pem projects/core/data/client_cert.pem > projects/core/data/client_combined.pem
PASS=$(cat projects/core/data/ca_passphrase.txt)
docker run -d --name runecore-server -v "${PWD}/projects/core/data:/data" -p 11440:11440 \
  -e RUNECORE_DATA_DIR=/data -e RUNECORE_CA_PASSPHRASE="$PASS" runecore-core:dev
```

6) Health check (over mTLS)

```bash
docker run --rm --network container:runecore-server -v "${PWD}/projects/core/data:/data" curlimages/curl:8.3.0 \
  sh -c "curl --cacert /data/ca_cert.pem --cert /data/client_combined.pem --resolve runecore.local:11440:127.0.0.1 https://runecore.local:11440/health"
```

7) Register a service (example payload)

Create `projects/core/data/payload.json`:

```json
{
  "name": "my-service",
  "version": "0.1",
  "rest_url": "https://example.local/api"
}
```

POST the payload with mTLS from an ephemeral container:

```bash
docker run --rm --network container:runecore-server -v "${PWD}/projects/core/data:/data" curlimages/curl:8.3.0 \
  sh -c "curl --cacert /data/ca_cert.pem --cert /data/client_combined.pem --resolve runecore.local:11440:127.0.0.1 -v \"https://runecore.local:11440/api/v1/services/register\" --data-binary @/data/payload.json -H \"Content-Type: application/json\""
```

Automated integration test

We provide a Dockerized integration script that automates the above flow (build, init, CSR generation, sign, run, mTLS POST and DB verification):

```bash
bash projects/core/test/run_integration.sh
```

CI note

There is a CI workflow at `.github/workflows/ci.yml` that runs `cargo test` and invokes the repository's Dockerized integration script. The integration script requires Docker on the runner and working network access to pull base images.

Troubleshooting & Windows notes

- If Docker fails pulling images, retry `docker pull debian:bookworm-slim` or `docker login` if you hit rate limits.
- On Windows, bind mounts can cause SQLite "unable to open database file" errors. Workaround: create the DB on the host and make it writable:

```bash
touch projects/core/data/runecore.db
chmod 666 projects/core/data/runecore.db
```

- The integration script already creates a writable DB file in a temp directory to avoid permission issues.

Alpha status and known gaps

This repository is alpha-ready: the Docker-first flow is implemented and an automated integration test exercises mTLS and the register endpoint. Before moving to beta/production consider:

- Implementing automated key rotation and a safe rollover strategy (currently manual/operational).
- Adding Docker HEALTHCHECK and verifying graceful shutdown (SIGTERM) behavior.
- Increasing test coverage and adding metrics/monitoring.

License

See the repository `LICENSE`.

docker build -t runecore-core:dev -f projects/core/Dockerfile projects/core

# Run container with a local data volume (interactive for logs)
docker run --rm -it -p 11440:11440 -v ${PWD}/projects/core/data:/data runecore-core:dev
```

Run tests inside the container (in builder image):

```powershell
# Start a shell in the builder image
docker run --rm -it -v ${PWD}:/usr/src/runecore_core -w /usr/src/runecore_core rust:1.72-slim bash
apt-get update && apt-get install -y pkg-config libssl-dev build-essential
cargo test
```
