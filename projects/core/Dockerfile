# Multi-stage Dockerfile for RuneCore Core
# Builder stage: use official Rust image and install OpenSSL dev packages
FROM rust:1.72-slim as builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libssl-dev \
    ca-certificates \
    git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/runecore_core

# Copy manifests first to leverage Docker cache
COPY Cargo.toml Cargo.lock ./
COPY src ./src

RUN cargo build --release

# Final runtime stage
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /usr/src/runecore_core/target/release/runecore_core ./runecore_core

ENV RUNECORE_DATA_DIR=/data
VOLUME ["/data"]

EXPOSE 11440

ENTRYPOINT ["/app/runecore_core"]
