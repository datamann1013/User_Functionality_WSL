# RuneCore Secrets Vault — Design Document

Status: **Draft / proposal** · Owner: Auronex · Target module: `RuneCore_Core` (or new `RuneCore_Vault` submodule) · Date: 2026-06-18

---

## 0. Summary

A Raft-replicated, envelope-encrypted secrets vault built into RuneCore_Core. Secrets
(today's `.env` values: `CA_PASSPHRASE`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`,
`REDIS_PASSWORD`, `INFLUX_PASSWORD`, `INFLUX_TOKEN`, …) are stored only as
AES-256-GCM ciphertext. Each secret is sealed under a per-vault **Data Encryption Key
(DEK)**; the DEK itself is sealed under a **master key** that lives in the host OS vault
(Windows DPAPI / Linux Secret Service / macOS Keychain). Core boots **sealed** — it holds
ciphertext but cannot read it — and **unseals** by asking the OS vault to release the
master key. This is the HashiCorp Vault seal/unseal shape adapted to the existing RuneCore
Raft cluster and CA crypto conventions.

The design deliberately reuses what already exists:
- The **Raft command/state-machine pattern** in `raft_consensus.rs` (we add a `VaultCommand` enum alongside `RegistryCommand`).
- The **AES-256-GCM + PBKDF2 envelope crypto** already shipping in `ca.rs`.
- The **Windows DPAPI wrapper** already shipping in `RuneCore_Marshal/src/dpapi.rs`.
- The **mTLS CN extraction + RBAC** pattern already shipping in `RuneCore_Marshal` (`tls.rs::extract_cn_from_der`, `rbac.rs::check`).

---

## 1. Goals / Non-Goals / Threat Model

### Goals
1. Remove plaintext secrets from `docker/.env`, `docker-compose.unified.yml`, and the git working tree.
2. Store secrets encrypted-at-rest, replicated across the cluster via the existing Raft pipeline so the HA node (`runecore_ha:11442`) has a copy.
3. Bind decryptability to the **physical host + active admin user** via the OS vault, so a stolen disk image or repo clone is useless without the OS-vault master key.
4. Reuse existing crypto + Raft + mTLS code; no new consensus layer, no new TLS stack.
5. Let services fetch their secrets from Core at startup over the existing mTLS channel, replacing `${VAR}` env interpolation.

### Non-Goals
- **Not** a defense against a compromised, *already-unsealed* Core process. Once unsealed, Core holds the DEK in RAM and can decrypt every secret. An attacker with code execution inside the running Core container (or root on the host) can read them. This is the same honest limitation HashiCorp Vault documents: the vault protects data at rest, not a live process whose memory is owned by the attacker.
- **Not** a per-user multi-tenant secrets system. RuneCore is a single-admin personal ecosystem; one human identity, one OS vault.
- **Not** an HSM/TPM-backed design in v1 (TPM sealing is listed as a future option in §6).
- **Not** a secret-rotation scheduler in v1 (manual/triggered rotation only).

### Threat model

| Threat | Protected? | Mechanism |
|---|---|---|
| Laptop/disk stolen, powered off | ✅ Yes | Master key sits in OS vault, itself bound to machine (DPAPI `CRYPTPROTECT_LOCAL_MACHINE`) and/or user login. Raft store holds ciphertext only. |
| Git repo / `.env` leaked | ✅ Yes | Secrets no longer live in repo; only ciphertext in the Raft data dir (which is `.gitignore`d). |
| Casual access by another local user | ⚠️ Partial | DPAPI machine scope means *any process on the machine* can call unprotect (see `dpapi.rs` note). Directory ACLs (SYSTEM + Administrators) are the real access gate. Linux keyring/Secret Service give per-user isolation. |
| Backup of Raft data dir copied off-box | ✅ Yes | Ciphertext only; master key never written to the Raft store or DB. |
| Compromised unsealed Core process | ❌ No | Out of scope — DEK is in RAM. |
| Root / Administrator on the live host | ❌ No | Can attach to the process or call OS-vault unprotect. Out of scope. |
| Malicious peer joining Raft | ⚠️ Mitigated, not solved | mTLS on the Raft transport (see §7 hardening dependency) limits who can `/api/v1/raft/message`. Today that endpoint trusts any CA-signed peer. |

---

## 2. Architecture

### 2.1 Envelope encryption layers

```
OS Vault (DPAPI / Secret Service / Keychain)
        │  holds: MASTER KEY  (32 bytes, AES-256)
        ▼
  unseal: Core asks OS vault to release master key into RAM
        │
        ▼
  WRAPPED DEK  (DEK encrypted under master key, AES-256-GCM)
  stored in Raft state machine as ciphertext
        │  unwrap with master key (in RAM only)
        ▼
  DEK  (32 bytes, AES-256, lives in RAM while unsealed)
        │  decrypt each secret
        ▼
  SECRET ciphertext (per-secret AES-256-GCM, nonce + ct)
  stored in Raft state machine
        ▼
  plaintext secret  (returned to authorized callers over mTLS)
```

Three independent layers means:
- **Rotate the master key** without touching any secret ciphertext — just re-wrap the single DEK (§6).
- **Rotate the DEK** by decrypting all secrets with the old DEK and re-encrypting with the new one — a bounded, infrequent operation.
- The Raft store and DB only ever see ciphertext (`WRAPPED DEK` + per-secret blobs).

### 2.2 Where things live

```
┌─────────────────────────── Host (Windows / Linux / macOS) ───────────────────────────┐
│                                                                                        │
│   OS Vault ──► master key                                                              │
│      ▲  (DPAPI CRYPTPROTECT_LOCAL_MACHINE on Win — reuse Marshal dpapi.rs)             │
│      │                                                                                  │
│   ┌──┴──────────────── RuneCore_Core container (node 1, :11440 / :11441) ───────────┐  │
│   │  Vault module                                                                    │  │
│   │   • SealState { Sealed | Unsealed }                                              │  │
│   │   • DEK (RAM only when Unsealed)                                                  │  │
│   │   • VaultStateMachine  ── applied via Raft, same as RegistryStateMachine         │  │
│   │   • /api/v1/vault/*  endpoints (mTLS, CN-based RBAC)                              │  │
│   │                                                                                   │  │
│   │   Raft pipeline (raft_consensus.rs / raft_network.rs / raft_storage.rs)           │  │
│   │     propose VaultCommand ──► replicate ──► apply to VaultStateMachine             │  │
│   └───────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────┘
                                   │ Raft over HTTP (mTLS) — /api/v1/raft/message
                                   ▼
┌──────────────── Other machine ────────────────┐
│  RuneCore_HA container (node 3, :11442)        │
│   • receives replicated WRAPPED DEK + secrets  │
│   • its own OS vault holds a master-key copy    │  (Option A, recommended — see §5)
│   • unseals independently                       │
└────────────────────────────────────────────────┘
```

### 2.3 Data stored in the Raft state machine

The vault adds a parallel state machine to the existing `RegistryStateMachine`
(`raft_consensus.rs`). It holds **only ciphertext**:

```rust
// new: vault state machine, mirrors RegistryStateMachine structure
struct VaultStateMachine {
    /// DEK wrapped under the master key. Replicated; useless without the OS-vault master key.
    wrapped_dek: Option<WrappedKey>,
    /// name -> sealed secret blob
    secrets: HashMap<String, SealedSecret>,
    last_applied: u64,
}

struct WrappedKey   { nonce: [u8;12], ciphertext: Vec<u8>, kdf_salt: Vec<u8>, version: u32 }
struct SealedSecret { nonce: [u8;12], ciphertext: Vec<u8>, dek_version: u32, updated_at: i64 }
```

Snapshot/restore reuses the exact `bincode::serialize` / `bincode::deserialize`
approach already used by `RegistryStateMachine::snapshot()` / `restore()` in
`raft_consensus.rs`. Because everything here is ciphertext, snapshots on disk
(`raft_storage.rs::persist_snapshot`) leak nothing.

---

## 3. OS Vault Integration (per platform)

### 3.1 What the OS vault stores

A single 32-byte master key, addressed by a fixed service/account name, e.g.
`("RuneCore", "vault-master-node-1")`. The OS vault is responsible for binding that
blob to the machine and/or the logged-in admin user.

### 3.2 Windows — DPAPI (reuse Marshal's existing code)

RuneCore_Marshal already ships a working DPAPI wrapper at
`projects/RuneCore_Marshal/src/dpapi.rs`:

- `inner::protect(data: &[u8]) -> Result<Vec<u8>, String>` — calls `CryptProtectData` with `CRYPTPROTECT_LOCAL_MACHINE`.
- `inner::unprotect(data: &[u8]) -> Result<Vec<u8>, String>` — calls `CryptUnprotectData`.
- Re-exported as `pub use inner::{protect, unprotect}` (Windows only; non-Windows builds fall back to plain files).

This is already consumed by `RuneCore_Marshal/src/tls.rs::load_key_bytes`, which checks
for a `<key_path>.dpapi` blob and calls `crate::dpapi::unprotect(&encrypted)` to decrypt
the Marshal private key at boot. **The vault should use the identical pattern**: store the
master key as a `vault_master.dpapi` blob, decrypt it on unseal via `unprotect`.

Caveat already documented in `dpapi.rs`: machine scope means *any process on the host*
can `unprotect`. The header comment notes the real access gate is the certs/ directory
ACL (SYSTEM + Administrators only). The vault master blob must live in a directory with
the same restrictive ACL. For stronger per-user binding, optionally add a non-empty
*entropy* argument to `CryptProtectData`/`CryptUnprotectData` (currently passed as
`ptr::null_mut()` in `dpapi.rs`) derived from an admin-supplied PIN — that would require a
small extension to the existing functions.

**Code sharing decision:** lift `dpapi.rs` into `shared_utils`-equivalent for Rust (a
small internal crate, e.g. `runecore_os_vault`) so both Marshal and Core/Vault link the
same implementation, rather than copy-pasting. Marshal already links `winapi` for DPAPI,
so the dependency footprint is proven.

### 3.3 Linux — Secret Service / kernel keyring

Two viable backends:
- **Secret Service (D-Bus)** — GNOME Keyring / KWallet. User-session-scoped; unlocks with the login keyring. Good UX on desktop installs.
- **Kernel keyring (`keyctl`, `user`/`session` keyrings)** — better for headless/server installs (the HA node may be headless). No D-Bus dependency.

For a Dockerized deployment the master key more realistically comes from the **host**, not
inside the container. Practical Linux options: bind-mount a host keyring path, or have a
tiny host-side helper (analogous to Marshal being a native host daemon on Windows) fetch
from Secret Service and hand the master key to the container over the existing mTLS loopback.

### 3.4 macOS — Keychain

`security`/Keychain Services, item class `kSecClassGenericPassword`, bound to the login
keychain. Future target only (Mac support is "a future option" per project memory).

### 3.5 Recommendation: `keyring` crate vs direct `windows` crate

**Use the [`keyring`](https://crates.io/crates/keyring) Rust crate as the cross-platform
abstraction, but keep Marshal's hand-rolled DPAPI path as the Windows backend.**

Rationale:
- `keyring` gives one API across Windows (Credential Manager), Linux (Secret Service / keyutils), and macOS (Keychain) — matches the project's tri-platform ambition.
- BUT `keyring`'s Windows backend uses **Credential Manager (user scope)**, whereas Marshal already standardized on **DPAPI machine scope** for at-rest key protection, and that code is battle-tested in `tls.rs`. Diverging would create two different Windows trust models in one ecosystem.
- So: define a `trait OsVault { fn store(name,&[u8]); fn load(name)->Vec<u8>; }`. Provide a `DpapiVault` impl (reusing `dpapi.rs`) as the default Windows backend, and a `KeyringVault` impl (the `keyring` crate) for Linux/macOS and as a Windows fallback. This honors "Marshal already links DPAPI" while not reinventing Linux/macOS.

---

## 4. Seal / Unseal Lifecycle

### 4.1 States

```
        boot
         │
         ▼
   ┌──────────┐  unseal (OS vault releases master key)   ┌────────────┐
   │  SEALED   │ ───────────────────────────────────────► │  UNSEALED  │
   │ ciphertext│                                           │ DEK in RAM │
   │  only      │ ◄─────────────────────────────────────── │            │
   └──────────┘            seal / shutdown / zeroize        └────────────┘
```

- **Sealed (boot default):** Vault state machine holds `wrapped_dek` + sealed secrets. No DEK in memory. `/api/v1/vault/read` returns `503 sealed`. Raft still runs, registry still works (the registry is independent of the vault).
- **Unseal:** Core asks the OS vault (`OsVault::load`) for the master key, unwraps `wrapped_dek` → DEK, holds DEK in RAM (ideally in a `zeroize`-on-drop buffer). Transitions to Unsealed.
- **Seal / shutdown:** zeroize the DEK and master key from RAM.

### 4.2 Auto-unseal vs manual

**Recommendation: auto-unseal on boot for this personal ecosystem.**

Justification:
- The whole point of the OS vault binding is that "the machine + admin login" *is* the unseal credential. If the admin is logged into their own machine, requiring a second manual unseal step adds friction without adding security against the threats we actually defend (disk theft, repo leak) — those are already defeated because a thief can't get the OS-vault master key.
- RuneCore is designed to come up unattended via `docker compose up`; a manual unseal would block every service that depends on secrets at startup.
- Manual unseal (HashiCorp's default) matters when the unseal key holders are *different people* than the operators. Here it's one admin. The OS vault is the human-presence proxy.

**Provide a manual override anyway:** a `/api/v1/vault/seal` endpoint and a config flag
`RUNECORE_VAULT_AUTO_UNSEAL=false` for paranoid/server scenarios, plus a manual
`/api/v1/vault/unseal` that accepts an admin-supplied passphrase (DPAPI entropy / age
passphrase) for the headless HA case.

---

## 5. The HA Unseal Problem

Node 3 (`runecore_ha:11442`, `RUNECORE_HA_MODE=1`) runs on a **separate machine**. Its OS
vault is a *different* OS vault. The replicated `wrapped_dek` was sealed under node 1's
master key, which node 3's OS vault does not hold. So node 3 receives the ciphertext via
Raft but, naively, cannot unseal.

### Option A — Per-node OS-vault-sealed master copy
Each node has its **own** master key in its **own** OS vault. The DEK is wrapped once per
node: the state machine stores `wrapped_dek_by_node: HashMap<NodeId, WrappedKey>`. When a
new node joins, the unsealed leader wraps the current DEK under the new node's public key
(or the operator provisions the new node's OS vault out-of-band during setup) and proposes
a `VaultCommand::AddNodeWrap`.

- **Pro:** No DEK ever crosses the network. Each node is independently unsealable. Strongest at-rest story; matches the existing per-node `ca_key.enc` philosophy.
- **Con:** Provisioning a new node requires an extra wrap step / operator action. Need an asymmetric step (node publishes a wrapping pubkey) so the leader can wrap for it without seeing the new node's master key.

### Option B — Primary forwards DEK to HA over existing mTLS post-unseal
HA boots sealed, asks the unsealed primary for the DEK over the existing mTLS channel
(the same one already used for `/api/v1/raft/message` and `/api/v1/services/*`). Primary
returns the raw DEK; HA holds it in RAM only, never persists it.

- **Pro:** Trivial to provision — new node just needs a valid client cert. No second OS vault required on the HA box.
- **Con:** The DEK transits the network (mTLS-protected, but still). If the HA box has no OS vault binding, a stolen HA disk image is fine (ciphertext only) BUT the HA box can never unseal on its own if the primary is down — defeats HA.

### Recommendation: **Option A as the target, with Option B as a bootstrap convenience.**

Use Option A (per-node master keys) for the durable design — it preserves the "each node's
secrets are bound to that node's OS vault" property and survives primary outage, which is
the entire reason the HA node exists. Allow Option B as an *opt-in bootstrap* path
(`RUNECORE_VAULT_HA_PULL_DEK=1`) for quick setup or a headless HA box that genuinely has no
usable OS vault, with the documented tradeoff that such a node cannot self-unseal offline.

---

## 6. Crypto Choices

| Concern | Choice | Grounding |
|---|---|---|
| Symmetric cipher | **AES-256-GCM** via the `aes-gcm` crate | Already a dependency and used in `ca.rs` (`Aes256Gcm::new_from_slice`, `cipher.encrypt(nonce, …)`). Reuse verbatim. |
| Key size | 256-bit master key, 256-bit DEK | Matches `ca.rs` 32-byte derived key. |
| Nonce | 96-bit (12 bytes), random per encryption via `getrandom::getrandom` | Exactly the pattern in `ca.rs` (`let mut nonce_bytes = [0u8;12]; getrandom::getrandom(&mut nonce_bytes)`). **One nonce per secret, never reused** — GCM nonce reuse is catastrophic, so generate fresh on every write. |
| Storage encoding | `nonce_b64 : ciphertext_b64` string, or bincode struct | `ca.rs` uses `format!("{}:{}", base64::encode(nonce), base64::encode(ct))`. The vault prefers a bincode `SealedSecret` struct (it's going through Raft `bincode` anyway) but the colon-format is an acceptable on-disk fallback. |
| KDF (for passphrase-derived unseal keys, e.g. manual unseal / HA) | **PBKDF2-HMAC-SHA256, 100_000 iters** | Matches `ca.rs::derive_key` exactly (`pbkdf2::<Hmac<Sha256>>(pass, salt, 100_000, &mut derived)`). **Improvement:** use a *random per-vault salt* stored in `WrappedKey.kdf_salt`, not the hardcoded `b"runecore_ca_salt"` — the hardcoded salt in `ca.rs` is a known weakness worth not repeating. Consider Argon2id for new code if a dependency add is acceptable. |
| OS-vault sealing | DPAPI (`dpapi.rs`) on Windows; `keyring` elsewhere | §3 |
| Optional `age` | `age` crate for the per-node *asymmetric* wrapping in Option A (§5) | `age`'s X25519 recipients are a clean way for the leader to wrap the DEK for a new node's public key without seeing its master key. Optional — only needed for Option A's join flow. |
| RNG | `getrandom` | Already used in `ca.rs`. |
| In-RAM hygiene | `zeroize` crate on DEK/master buffers | New, small dependency. Not present today but cheap and important. |

### Rotation strategy
- **Master-key rotation (cheap, frequent-OK):** generate new master key in OS vault → unwrap DEK with old master → re-wrap DEK with new master → propose `VaultCommand::RewrapDek`. **No secret is re-encrypted.** This is the headline benefit of the DEK layer.
- **DEK rotation (heavier, rare):** generate new DEK → for each secret: decrypt with old DEK, re-encrypt with new DEK, bump `dek_version` → propose a batch `VaultCommand::RotateDek`. Keep old DEK wrapped until all secrets are migrated (track via `dek_version`).
- **Per-secret rotation:** just `PUT` a new value (a new `VaultCommand::PutSecret`).

---

## 7. API Surface

New endpoints on Core, registered in `main.rs` alongside the existing
`/api/v1/services/*` and `/api/v1/raft/message` routes (see `main.rs` route table
~lines 156–174). All vault routes require mTLS (no `RUNECORE_DISABLE_MTLS` bypass for
vault) and CN-based RBAC.

| Method + Path | Action key | Description |
|---|---|---|
| `GET  /api/v1/vault/status` | `vault.status` | `{ sealed: bool, secret_count, dek_version }`. No plaintext. |
| `POST /api/v1/vault/unseal` | `vault.unseal` | Manual unseal (auto-unseal path runs at boot). |
| `POST /api/v1/vault/seal` | `vault.seal` | Zeroize DEK, return to sealed. |
| `GET  /api/v1/vault/secrets` | `vault.list` | List secret **names + metadata only**, never values. |
| `GET  /api/v1/vault/secret/{name}` | `vault.read` | Return decrypted secret to authorized CN. `503` if sealed. |
| `PUT  /api/v1/vault/secret/{name}` | `vault.write` | Encrypt + propose `VaultCommand::PutSecret`. |
| `DELETE /api/v1/vault/secret/{name}` | `vault.delete` | Propose `VaultCommand::DeleteSecret`. |
| `POST /api/v1/vault/rotate/master` | `vault.rotate.master` | Re-wrap DEK (§6). |
| `POST /api/v1/vault/rotate/dek` | `vault.rotate.dek` | Re-encrypt all secrets (§6). |

### Authorization (reuse Marshal's RBAC model)
Core does not yet have per-CN RBAC — `main.rs` only *logs* the client cert subject during
verification (~lines 238–248) and uses a wrapped verifier. **Adopt Marshal's pattern:**
- Extract the caller CN exactly as `RuneCore_Marshal/src/tls.rs::extract_cn_from_der` does (x509-parser, `OID_X509_COMMON_NAME`), inject it as an axum extension (Marshal's `main.rs` ~line 217 does this via a custom acceptor and a `CallerCn` extension).
- Check it with the same shape as `RuneCore_Marshal/src/rbac.rs::check(cfg, caller_cn, action)`, including its `"service.*"` wildcard-suffix matching — vault actions like `vault.*` slot right in.
- Define roles in Core's TOML config mirroring Marshal's `RoleConfig { caller_cn, allowed_actions }` (`config.rs`). Example: only the admin's personal client cert CN gets `vault.read`/`vault.write`; each service CN (e.g. `core_memory_api`, matching the cert CNs already used in `service_discovery.py`) gets `vault.read` scoped to its own secret prefix.

### New Raft command type (mirror `RegistryCommand`)
Add to `raft_consensus.rs`, applied identically to how `process_ready()` decodes and
applies `RegistryCommand` today:

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VaultCommand {
    InitVault   { wrapped_dek: WrappedKey },          // first-boot: create DEK, wrap, store
    PutSecret   { name: String, sealed: SealedSecret },
    DeleteSecret{ name: String },
    RewrapDek   { wrapped_dek: WrappedKey },           // master rotation
    RotateDek   { wrapped_dek: WrappedKey, secrets: HashMap<String, SealedSecret> },
    AddNodeWrap { node_id: u64, wrapped_dek: WrappedKey }, // Option A HA join
}
```

`propose(VaultCommand)` follows `RaftManager::propose` verbatim (`bincode::serialize` →
`node.propose(vec![], data)`). `VaultStateMachine::apply(index, cmd)` mirrors
`RegistryStateMachine::apply`. In `process_ready()`'s committed-entries loop, attempt to
`bincode::deserialize::<RegistryCommand>` first, then `::<VaultCommand>` (or tag entries
with a 1-byte discriminator to avoid ambiguous decode). **Plaintext secrets are never
proposed — only sealed blobs.**

---

## 8. Migration Plan

Today's secrets (from `docker/.env.sample` and `docker-compose.unified.yml`):

| Secret | Where used today |
|---|---|
| `CA_PASSPHRASE` → `RUNECORE_CA_PASSPHRASE` | Core/HA/secondary (compose lines 72, 108, 140) — feeds `ca.rs::init_ca`/`load_encrypted_key` |
| `JWT_SECRET_KEY` | AI backend (compose line 210) |
| `POSTGRES_PASSWORD` | postgres + `DATABASE_URL` (lines 249, 298) |
| `REDIS_PASSWORD` | redis `--requirepass` + `REDIS_URL` (lines 264, 271, 299) |
| `INFLUX_PASSWORD` | influx init (line 282) |
| `INFLUX_TOKEN` | influx admin token + memory service (lines 285, 301) |

**Bootstrapping chicken-and-egg:** `CA_PASSPHRASE` unlocks the CA which mints the mTLS
certs that the vault API requires. So `CA_PASSPHRASE` **cannot** be the first thing fetched
from the vault over mTLS. Resolution: the **master key (and `CA_PASSPHRASE` itself)** is
sealed directly by the OS vault at the Core layer, *not* served over the vault API. The
OS-vault → master-key → CA-passphrase chain is the root of trust; everything else is
fetched over mTLS once the CA is up.

### Phased rollout (backward-compatible at every step)
1. **Phase 0 — shadow.** Ship the vault sealed/unsealed plumbing. Vault is populated but nothing reads from it yet. `.env` still authoritative. Verify replication to HA.
2. **Phase 1 — Core-internal secrets.** Move `CA_PASSPHRASE` into the OS-vault-sealed root. Core reads it from the vault layer instead of `RUNECORE_CA_PASSPHRASE` env. Fall back to env if vault sealed (logged warning).
3. **Phase 2 — service secrets via API.** Services fetch their secret(s) at startup over mTLS, reusing the **exact `service_discovery.py` pattern**: it already loads `(CERT_PATH, KEY_PATH)`/`CA_CERT_PATH` and calls `GET /api/v1/services/query`. Add a sibling `get_secret(name)` that calls `GET /api/v1/vault/secret/{name}` with the same `cert=`, `verify=` mTLS config. Keep env-var fallback: `value = vault.get_secret(name) or os.environ[name]`.
4. **Phase 3 — compose cleanup.** Replace `${POSTGRES_PASSWORD}` etc. with vault fetches inside each service entrypoint. For containers that *can't* easily call the API at the right moment (e.g. the `postgres` image reading `POSTGRES_PASSWORD` at init), use an entrypoint shim that fetches the secret and exports it before exec'ing the real entrypoint. `.env` shrinks to non-secret config only.
5. **Phase 4 — remove plaintext.** Delete secret rows from `.env`/compose; `.env.sample` documents "secrets now live in the vault; run `runecore vault put …` to seed."

---

## 9. Open Questions / Decisions for the User

1. **Module placement:** Build the vault *inside* `RuneCore_Core` (shares Raft/CA/DB directly, simplest) or as a separate `RuneCore_Vault` submodule (cleaner boundary, but must talk to Core's Raft remotely)? Recommendation: **inside Core** for v1 — it needs the same Raft node and CA.
2. **HA unseal:** Confirm **Option A (per-node master)** as target. Are you OK with the extra node-provisioning step, or do you want Option B's convenience for the current 2-box setup?
3. **DPAPI entropy / PIN:** Do you want a per-vault admin PIN feeding DPAPI entropy (defends against *other local users on the same Windows box*), or is the directory-ACL gate enough for a single-admin machine?
4. **Salt fix:** OK to use a random per-vault salt (and store it) instead of `ca.rs`'s hardcoded `b"runecore_ca_salt"`? (Strongly recommended.)
5. **Auto-unseal default:** Confirm auto-unseal ON by default with manual override flag.
6. **Postgres/Redis init secrets:** Acceptable to add entrypoint shims to those official images, or do you prefer to keep DB bootstrap creds in `.env` and only vault the application-level secrets?
7. **Raft transport hardening:** §10 — the vault's safety depends on `/api/v1/raft/message` being mTLS-authenticated. Today the transport in `raft_network.rs` posts plain `application/octet-stream` over `http://` peer URLs. Is hardening Raft mTLS in scope before vault GA?
8. **`age` dependency:** OK to add the `age` crate for Option A's asymmetric node-join wrapping, plus `keyring` and `zeroize`?

---

## 10. Implementation Phases

> Likely lives in `RuneCore_Core` (decision §9.1). **Hard dependency: Core Raft hardening** — the vault replicates ciphertext over the Raft transport, and that transport (`raft_network.rs`) currently sends over plain HTTP with no peer authentication. The wrapped DEK is safe in transit even so (it's useless without an OS-vault master key), but a malicious peer could *inject* `VaultCommand`s. Raft-over-mTLS (or signed Raft messages) should land before the vault is trusted for real secrets.

| Phase | Scope | Key files |
|---|---|---|
| **P0 — Crypto + OS-vault trait** | `OsVault` trait; `DpapiVault` (lift `dpapi.rs` into a shared crate); `KeyringVault`; envelope encrypt/decrypt reusing `ca.rs` AES-GCM/PBKDF2 (with random salt + `zeroize`). Unit tests. | new `runecore_os_vault` crate; new `vault/crypto.rs` |
| **P1 — Vault state machine + Raft command** | `VaultCommand`, `VaultStateMachine`, snapshot/restore; wire decode into `process_ready()`. | `raft_consensus.rs` |
| **P2 — Seal/unseal lifecycle** | `SealState`, boot-sealed, auto-unseal via `OsVault::load`, `InitVault` on first boot, DEK held in zeroizing buffer. | new `vault/seal.rs`, `main.rs` |
| **P3 — API + RBAC** | `/api/v1/vault/*` routes; CN extraction (port Marshal `tls.rs::extract_cn_from_der`) + RBAC (port `rbac.rs::check`); roles in Core TOML config. | `main.rs`, new `vault/api.rs`, `config` |
| **P4 — HA replication** | Option A per-node wrapping (`AddNodeWrap`, `age` join flow); verify node 3 unseals independently. | `vault/seal.rs`, `raft_consensus.rs` |
| **P5 — Migration** | `runecore vault put/get/list` CLI; `service_discovery.py` `get_secret()`; entrypoint shims; phased `.env` retirement (§8). | `cli.rs`, `service_discovery.py`, compose entrypoints |
| **P6 — Rotation** | master rewrap + DEK rotate endpoints/CLI. | `vault/api.rs`, `vault/crypto.rs` |

---

### Appendix: files read to ground this design
- `projects/RuneCore_Core/src/raft_consensus.rs` — `RegistryCommand` enum, `RegistryStateMachine::{apply,snapshot,restore}`, `RaftManager::{propose,process_ready}`, `bincode` serialization.
- `projects/RuneCore_Core/src/raft_storage.rs` — `PersistentStorage`, atomic snapshot/hard-state persistence.
- `projects/RuneCore_Core/src/raft_network.rs` — `RaftTransport` (plain HTTP `application/octet-stream`), `/api/v1/raft/message`, `raft_network_task`.
- `projects/RuneCore_Core/src/ca.rs` — `Aes256Gcm`, `pbkdf2::<Hmac<Sha256>>(…,100_000,…)`, hardcoded `b"runecore_ca_salt"`, `getrandom` 12-byte nonce, `nonce_b64:ct_b64` storage, `init_ca`/`load_encrypted_key`/`get_server_cert_and_key_pem`.
- `projects/RuneCore_Core/src/db.rs` — SQLite `services` table, `init_db` with `create_if_missing`.
- `projects/RuneCore_Core/src/main.rs` — route table (~156–174), `RUNECORE_ENABLE_RAFT`/`RAFT_NODE_ID`/`RAFT_PEER_URLS`/`RUNECORE_HA_MODE`/`RUNECORE_DISABLE_MTLS`, client-cert logging (~238–248).
- `projects/RuneCore_Marshal/src/dpapi.rs` — `protect`/`unprotect`, `CRYPTPROTECT_LOCAL_MACHINE`, machine-scope caveat, null entropy.
- `projects/RuneCore_Marshal/src/tls.rs` — `load_key_bytes` `.dpapi` path, `extract_cn_from_der`.
- `projects/RuneCore_Marshal/src/rbac.rs` + `config.rs` — `check(cfg, caller_cn, action)`, `"service.*"` wildcard, `RoleConfig { caller_cn, allowed_actions }`.
- `projects/RuneCore_Memory/core_memory/service_discovery.py` — mTLS client (`get_mtls_config`, `cert=`, `verify=`), `register_with_core`, `get_service_url`.
- `docker/.env.sample` + `docker/docker-compose.unified.yml` — enumerated secrets and their usage lines.
