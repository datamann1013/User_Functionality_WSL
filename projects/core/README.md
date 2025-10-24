# RuneCore Core (Rust) - Skeleton

This is an initial Rust skeleton for the RuneCore Core microservice. It provides:

- Minimal Axum-based HTTP server
- In-memory service registry with register/list endpoints
- CA initialization that generates a self-signed root certificate and stores an encrypted private key on disk. The CA private key is encrypted using a PBKDF2-derived key from a passphrase provided via environment variable.

Environment variables:
- `RUNECORE_CA_PASSPHRASE` (required): passphrase used to encrypt the CA private key on disk.
- `RUNECORE_DATA_DIR` (optional): path to store CA key/cert and other runtime data (default: `./data`).

Build & run:

1. Install Rust toolchain (1.70+).
2. From this folder run:

```powershell
cargo run --manifest-path .\Cargo.toml
```

The server will listen on `127.0.0.1:11440` by default. This is a starting point — next steps will add SQLite persistence, mTLS, and APIs for configuration and PKI operations.
