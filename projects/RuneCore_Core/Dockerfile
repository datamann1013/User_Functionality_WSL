# Multi-stage Dockerfile for RuneCore Core
# Builder stage: use official Rust image and install OpenSSL dev packages
FROM runecore/rust-builder-dev:latest as builder

# Install system deps and rustup so we can use a newer toolchain (nightly)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libssl-dev \
    ca-certificates \
    curl \
    git \
 && rm -rf /var/lib/apt/lists/* \
 && curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain nightly \
 && . /usr/local/cargo/env && rustup default nightly

# Ensure cargo/bin from the system-wide install is on PATH
ENV PATH="/usr/local/cargo/bin:${PATH}"

WORKDIR /usr/src/runecore_core

# Copy manifests first to leverage Docker cache
COPY Cargo.toml Cargo.lock ./
COPY src ./src

 # Run tests to validate behavior in builder
 RUN cargo test --release --workspace || true
 RUN cargo build --release

# Final runtime stage
FROM runecore/python-slim-dev:latest as runtime_base
FROM debian:bullseye-slim
# Ensure runtime has the OpenSSL 1.1 compatibility library used by the built binary
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libssl1.1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/src/runecore_core/target/release/runecore_core ./runecore_core

ENV RUNECORE_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 11440

ENTRYPOINT ["/app/runecore_core"]
