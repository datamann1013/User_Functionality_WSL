# Multi-stage Dockerfile for RuneCore Core
# runecore/rust-builder-dev already has Rust 1.83 stable + build tools
FROM runecore/rust-builder-dev:latest as builder

WORKDIR /usr/src/runecore_core

# Install nightly toolchain — required by home 0.5.12 (edition2024) and other deps
RUN rustup install nightly --no-self-update && rustup default nightly

# Copy manifests first to leverage Docker cache
COPY Cargo.toml Cargo.lock ./
COPY src ./src

RUN cargo +nightly build --release

# Final runtime stage — Bullseye matches builder OS for libssl1.1 compatibility
FROM debian:bullseye-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl1.1 \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/src/runecore_core/target/release/runecore_core ./runecore_core

ENV RUNECORE_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 11440

ENTRYPOINT ["/app/runecore_core"]
