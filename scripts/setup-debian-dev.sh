#!/usr/bin/env bash
# Debian/Ubuntu/Kali developer setup for RuneCore_Sentinel
set -euo pipefail

echo "Updating apt and installing build dependencies..."
sudo apt update
sudo apt install -y build-essential pkg-config curl ca-certificates libssl-dev musl-tools gcc-multilib

echo "Installing rustup (non-interactive)..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
export PATH="$HOME/.cargo/bin:$PATH"

echo "Adding recommended Rust components and targets"
rustup component add rustfmt clippy || true
rustup target add x86_64-unknown-linux-gnu || true
rustup target add x86_64-unknown-linux-musl || true

echo "Debian dev setup complete. Open a new shell or source ~/.cargo/env to pick up rustup"
