#!/usr/bin/env bash
# Arch/Manjaro developer setup for RuneCore_Sentinel
set -euo pipefail

echo "Updating pacman and installing development packages..."
sudo pacman -Syu --noconfirm
sudo pacman -S --noconfirm base-devel openssl pkgconf curl musl

echo "Installing rustup (non-interactive)..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
export PATH="$HOME/.cargo/bin:$PATH"

echo "Adding recommended Rust components and targets"
rustup component add rustfmt clippy || true
rustup target add x86_64-unknown-linux-gnu || true
rustup target add x86_64-unknown-linux-musl || true

echo "Arch dev setup complete. Open a new shell or source ~/.cargo/env to pick up rustup"
