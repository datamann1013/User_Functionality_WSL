# RuneDrop (projects/RuneCore_Drop)

RuneDrop is the planned file-sharing module for RuneCore (folder name: `RuneCore_Drop`, module name: `RuneDrop`).

This repository contains a minimal Rust-based prototype (Actix-web) implementing an HTTP relay upload/download flow with short-lived tokens and QR generation. It is an MVP — P2P (WebRTC) will be added in a follow-up iteration.

Features implemented in this prototype:
- POST /upload — multipart/form-data file upload. Returns file_id, token, download URL and a QR (SVG) that encodes the download URL.
- GET /download/{file_id}?token=... — download the uploaded file (attachment)
- GET /health — basic health check
- Best-effort auto-registration with RuneCore core at startup (environment variable `RUNECORE_CORE_URL`)
 - Signaling endpoints for P2P (polling-based):
	 - POST /signal/{file_id} — append a JSON string message (offer/answer/ice)
	 - GET /signal/{file_id}?from=N — get messages from index N onward

Frontend
- A minimal React-based single-file frontend is included at `frontend/index.html` (no build step): it supports both HTTP relay flow and P2P via WebRTC datachannel using the signaling endpoints. Upload returns an SVG QR which the frontend displays.

Configuration
- PORT — service port (default 5010)
- RUNECORE_CORE_URL — core registration endpoint (default http://localhost:5000/api/modules/register)

Storage
- Files are stored in `./storage/uploads/` inside the container. Metadata persisted to `./storage/metadata.json`.

Notes
- The prototype uses TLS only if fronted by a reverse-proxy or the core provides certificates. The crate opts to accept invalid certs during the initial registration call to the core to allow local CA setups; change this behavior for production.
- Token expiry default: 48 hours. The frontend should keep the QR displayed while the user intends the file to be available.

Next steps (can implement next):
- Add P2P support (WebRTC signaling + datachannel) so transfers can be direct between devices when possible.
- Add React frontend for drag-and-drop and QR/pairing UI (currently the endpoint returns SVG QR which a frontend can display).
- Implement at-rest encryption option and TLS integration with the core-provided certs.
