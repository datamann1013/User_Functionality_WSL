#!/usr/bin/env bash
# Generate self-signed dev certs for RuneCore_Marshal.
# Run from Git Bash in the project directory:
#   bash gen_dev_certs.sh
#
# Outputs to:
#   certs_dev/  — keep these (CA key, test client certs)
#   C:/RuneCore/marshal/certs/  — marshal.crt, marshal.key, ca.crt (live certs)
#
# NOTE: For production, replace with certs issued by RuneCore_Core's CA.

set -e

# Prevent Git Bash from converting /CN=... paths to Windows paths (e.g. C:/Program Files/Git/CN=...)
export MSYS_NO_PATHCONV=1

OUT="certs_dev"
DEPLOY="C:/RuneCore/marshal/certs"

mkdir -p "$OUT"
mkdir -p "$DEPLOY"

echo "==> Generating CA..."
openssl genrsa -out "$OUT/ca.key" 2048
openssl req -new -x509 -days 3650 \
    -key "$OUT/ca.key" \
    -out "$OUT/ca.crt" \
    -subj "/CN=RuneCore-Dev-CA"

echo "==> Generating Marshal server cert..."
openssl genrsa -out "$OUT/marshal.key" 2048
openssl req -new \
    -key "$OUT/marshal.key" \
    -out "$OUT/marshal.csr" \
    -subj "/CN=marshal"

cat > "$OUT/server_ext.cnf" <<EOF
[v3_server]
subjectAltName = IP:127.0.0.1,DNS:localhost
keyUsage = digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
EOF

openssl x509 -req -days 730 \
    -in "$OUT/marshal.csr" \
    -CA "$OUT/ca.crt" \
    -CAkey "$OUT/ca.key" \
    -CAcreateserial \
    -out "$OUT/marshal.crt" \
    -extensions v3_server \
    -extfile "$OUT/server_ext.cnf"

echo "==> Generating test client cert (CN=ollama_wrapper)..."
openssl genrsa -out "$OUT/ollama_wrapper.key" 2048
openssl req -new \
    -key "$OUT/ollama_wrapper.key" \
    -out "$OUT/ollama_wrapper.csr" \
    -subj "/CN=ollama_wrapper"
openssl x509 -req -days 730 \
    -in "$OUT/ollama_wrapper.csr" \
    -CA "$OUT/ca.crt" \
    -CAkey "$OUT/ca.key" \
    -CAcreateserial \
    -out "$OUT/ollama_wrapper.crt"

echo "==> Deploying to $DEPLOY..."
cp "$OUT/ca.crt"      "$DEPLOY/ca.crt"
cp "$OUT/marshal.crt" "$DEPLOY/marshal.crt"
cp "$OUT/marshal.key" "$DEPLOY/marshal.key"

echo ""
echo "Done. Certs deployed to $DEPLOY"
echo "  ca.crt      — CA certificate (add to clients that call Marshal)"
echo "  marshal.crt — Marshal server certificate"
echo "  marshal.key — Marshal server private key"
echo ""
echo "Test client certs in $OUT/:"
echo "  ollama_wrapper.crt / .key  — use to test RBAC from curl/wrapper"
echo ""
echo "Restart Marshal service to pick up the new certs:"
echo "  sc.exe start RuneCore-Marshal"
