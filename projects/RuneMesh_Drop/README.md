# RuneMesh_Drop

File transfer module for RuneCore ecosystem (folder: `RuneMesh_Drop`, module: `RuneMesh_Drop`).

## MVP Status

This is the **MVP** implementation with:
- Rust/Actix-web backend with HTTP upload/download + QR code generation
- New React/Vite frontend with matching Steel Blue theme
- Core registration as `RuneMesh_Drop` with `file_transfer` and `qr_code` capabilities
- Behind Core proxy (port 11441) - not directly exposed

## Features

### Backend (Rust/Actix-web)
- `POST /upload` — multipart/form-data file upload. Returns file_id, token, download URL and QR (SVG)
- `GET /download/{file_id}?token=...` — download the uploaded file
- `GET /interfaces` — network interface detection for QR URL generation
- `GET /health` — basic health check
- Auto-registration with RuneCore Core at startup
- Signaling endpoints for P2P (stub, not fully implemented)

### Frontend (React/Vite)
- Send File panel with drag-and-drop zone
- Network interface selector
- QR code display (SVG rendered)
- Copyable download link
- Receive File panel with manual code/URL entry
- Recent transfers list (localStorage persisted)

## Configuration

- `PORT` — service port (default 5010)
- `RUNECORE_CORE_URL` — core registration endpoint (default http://localhost:5000/api/modules/register)
- `RUNECORE_ALLOW_INSECURE_REGISTRATION` — allow insecure TLS for dev (set to "true")

## Docker Compose (Dev)

```yaml
services:
  mesh_drop:
    build: .
    environment:
      - PORT=5010
      - RUNECORE_CORE_URL=http://runecore_core:11441
      - RUNECORE_ALLOW_INSECURE_REGISTRATION=true
    networks:
      runecore_dev:
        aliases:
          - mesh_drop
```

## Access

- Direct: http://localhost:5100 (mapped port)
- Via Core proxy: http://localhost:11441/api/proxy/RuneMesh_Drop/...

## Storage

- Files: `./storage/uploads/` inside container
- Metadata: `./storage/metadata.json`

## Token

- Default expiry: 48 hours
- Token validation required for download

## Future (Not in MVP)

- P2P via WebRTC
- mDNS/UPnP for device discovery
- End-to-end encryption
