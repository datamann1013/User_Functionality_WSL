#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
DATA_DIR=$(mktemp -d)/data
mkdir -p "$DATA_DIR"

echo "Building Docker image..."
docker build -t runecore-core:ci -f "$ROOT_DIR/Dockerfile" "$ROOT_DIR"

echo "Initializing core (creating CA + server cert)..."
docker run --rm -v "$DATA_DIR:/data" runecore-core:ci init-core --data-dir /data

# Ensure SQLite DB file exists (some host mounts need the file to be present for sqlite3 to open it)
echo "Creating empty runecore.db to avoid sqlite open errors"
docker run --rm -v "$DATA_DIR:/data" busybox sh -c "touch /data/runecore.db; chmod 666 /data/runecore.db" || true

echo "Generating client key and CSR..."
docker run --rm -v "$DATA_DIR:/data" debian:bookworm-slim bash -lc "apt-get update >/dev/null && apt-get install -y --no-install-recommends openssl >/dev/null && openssl genrsa -out /data/client_key.pem 2048 && openssl req -new -key /data/client_key.pem -subj '/CN=test-client' -out /data/client.csr"

echo "Signing client CSR using container CLI..."
docker run --rm -v "$DATA_DIR:/data" runecore-core:ci sign-csr --data-dir /data --csr-file /data/client.csr --out /data/client_cert.pem --role client

echo "Combining client key + cert into single PEM..."
docker run --rm -v "$DATA_DIR:/data" alpine:3.18 sh -c "cat /data/client_key.pem /data/client_cert.pem > /data/client_combined.pem"

PASS=$(cat "$DATA_DIR/ca_passphrase.txt")

echo "Starting server container..."
docker rm -f runecore-server >/dev/null 2>&1 || true
docker run -d --name runecore-server -v "$DATA_DIR:/data" -p 11440:11440 -e RUNECORE_DATA_DIR=/data -e RUNECORE_CA_PASSPHRASE="$PASS" runecore-core:ci

echo "Waiting for server to become healthy (using mTLS)..."
for i in {1..20}; do
  if docker run --rm --network container:runecore-server -v "$DATA_DIR:/data" curlimages/curl:8.3.0 sh -c "curl --silent --fail --cacert /data/ca_cert.pem --cert /data/client_combined.pem https://runecore.local:11440/health --resolve runecore.local:11440:127.0.0.1" >/dev/null 2>&1; then
    echo "Server responded to health check"
    break
  fi
  echo "Waiting... ($i)"
  sleep 1
done

echo "Posting registration payload..."
cat > "$DATA_DIR/payload.json" <<'EOF'
{
  "name": "integration-test-service",
  "version": "0.1",
  "rest_url": "https://example.local/api",
  "public_key_pem": null
}
EOF

docker run --rm --network container:runecore-server -v "$DATA_DIR:/data" curlimages/curl:8.3.0 sh -c "curl --cacert /data/ca_cert.pem --cert /data/client_combined.pem --resolve runecore.local:11440:127.0.0.1 -sS -o /tmp/resp.json -w '%{http_code}' https://runecore.local:11440/api/v1/services/register --data-binary @/data/payload.json -H 'Content-Type: application/json'" > "$DATA_DIR/last_status" || true

STATUS=$(cat "$DATA_DIR/last_status")
echo "HTTP status: $STATUS"
if [ "$STATUS" != "200" ] && [ "$STATUS" != "201" ]; then
  echo "Registration failed, dumping server logs:" >&2
  docker logs runecore-server >&2 || true
  exit 2
fi

echo "Verifying DB entry..."
docker run --rm -v "$DATA_DIR:/data" nouchka/sqlite3 /data/runecore.db "SELECT COUNT(*) FROM services;" | grep -q '[1-9]' || (echo "No rows in services table" && exit 3)

echo "Integration test succeeded"

# Cleanup (leave artifacts for debugging if you want)
docker rm -f runecore-server >/dev/null 2>&1 || true
rm -rf "$DATA_DIR"
