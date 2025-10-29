RuneCore Integration Contract (Alpha)

Purpose
-------
This document defines the minimal integration contract for the Alpha ecosystem. The RuneCore Core service is the canonical authority for service registration, PKI (signing CSRs), and service discovery. Services SHOULD follow this contract to interoperate securely and predictably.

Transport & Ports
-----------------
- Core: HTTPS (TLS) server on port 11440 by default. Environment variable `RUNECORE_CORE_PORT` may be used in testing. Core presents a server certificate signed by the RuneCore CA.
- Services: may expose REST or WebSocket endpoints on any port; they SHOULD publish their reachable `rest_url`/`ws_url` during registration.

Authentication & Encryption
---------------------------
- mTLS is the default for service-to-core communications. Services MUST present a client certificate signed by the RuneCore CA when `RUNECORE_DISABLE_MTLS` is not set.
- For development only, `RUNECORE_DISABLE_MTLS=1` or `RUNECORE_ALLOW_INSECURE_REGISTRATION=true` allows plain HTTPS or HTTP registration. This MUST NOT be used in staging/production.
- Client TLS options (client cert/key path, CA path) are passed via environment variables:
  - `RUNECORE_CLIENT_CERT_PATH`
  - `RUNECORE_CLIENT_KEY_PATH`
  - `RUNECORE_CORE_CA_PATH`
  - `RUNECORE_DISABLE_MTLS` (opt-out, debug)

API Endpoints (Core)
--------------------
- POST /api/v1/services/register
  - Body: JSON ServiceInfo { name, version?, rest_url?, ws_url?, public_key_pem? }
  - Response: { ok: true, service_id }
- GET /api/v1/services
  - Returns list of registered services
- POST /api/v1/pki/sign
  - Body: { csr_pem: string, days_valid?: number }
  - Returns: { ok: true, cert_pem }

Message Formats
---------------
- All API calls use application/json for bodies unless otherwise specified.
- ServiceInfo minimal fields for registration:
  - name: string (required)
  - version: string (optional)
  - rest_url: string (optional)
  - ws_url: string (optional)
  - public_key_pem: string (optional)

Error handling
--------------
- 4xx and 5xx HTTP responses are used per standard REST semantics. Services should retry idempotent operations like registration with exponential backoff when receiving 5xx or network errors.

Testing guidance
----------------
- Unit tests should mock network I/O. Use the shared `core_client` helper to centralize TLS handling and make tests deterministic.
- Integration tests SHOULD exercise:
  - Successful mTLS registration
  - Fallback registration when mTLS disabled
  - CSR signing flow using a test CA (or stubbed sign endpoint)

Backward compatibility
----------------------
- Core will accept JSON registration requests even when Content-Type is missing. Services should set Content-Type: application/json when possible.

Notes
-----
- This contract is intentionally minimal and conservative for Alpha. As the system matures, the contract will be versioned and extended.
