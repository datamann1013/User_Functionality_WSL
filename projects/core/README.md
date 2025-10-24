# RuneCore Core (Rust) - Skeleton

This is an initial Rust skeleton for the RuneCore Core microservice. It provides:

- Minimal Axum-based HTTP server
- In-memory service registry with register/list endpoints
- CA initialization that generates a self-signed root certificate and stores an encrypted private key on disk. The CA private key is encrypted using a PBKDF2-derived key from a passphrase provided via environment variable.

Environment variables:
- `RUNECORE_CA_PASSPHRASE` (optional): passphrase used to encrypt the CA private key on disk. If not provided, the CLI helper will create `data/ca_passphrase.txt`.
- `RUNECORE_DATA_DIR` (optional): path to store CA key/cert and other runtime data (default: `./data`).


CLI helpers:

1) Create a passphrase file and initialize CA:

```powershell
# create passphrase and CA under ./data
cargo run -- InitCore --data-dir .\data

# or create only a passphrase file
cargo run -- InitPassphrase --data-dir .\data
```

This writes:

- `data/ca_passphrase.txt` — passphrase (base64) used to encrypt the CA private key
- `data/ca_key.enc` — encrypted CA private key
- `data/ca_cert.pem` — public CA certificate

PKI endpoints:

- POST /api/v1/pki/sign
	- JSON body: { "csr_pem": "-----BEGIN CERTIFICATE REQUEST-----...", "days_valid": 7 }
	- Returns: { "ok": true, "cert_pem": "-----BEGIN CERTIFICATE-----..." }

Build & run server (development):

```powershell
setx RUNECORE_DATA_DIR .\data
setx RUNECORE_CA_PASSPHRASE <your-passphrase>
cargo run
```

Tests:

```powershell
cargo test
```

Notes:
- This skeleton uses native OpenSSL. On Windows you must have OpenSSL development libraries installed or use vcpkg and set `OPENSSL_DIR` so `openssl-sys` can build.
- In production we will run the core inside Docker; the Dockerfile should install OpenSSL dev packages and then build the binary.
Docker build & run (recommended for consistent builds):

```powershell
# Build the docker image from project root
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
