# Multi-stage Dockerfile for RuneDev_Code (runecode)
# Provides OS-level isolation: the agent runs as a non-root user with /workspace
# as its only writable mount. This is the real isolation boundary; the in-binary
# sandbox/denylist (src/security.rs) is defence-in-depth on top.

# ----- build stage (stable Rust; reqwest default-tls needs libssl-dev) -----
FROM rust:1-bookworm AS build
WORKDIR /build
# Cache deps: copy manifests first
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

# ----- runtime stage -----
FROM debian:bookworm-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        libssl3 \
        git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin runecode

COPY --from=build /build/target/release/runecode /usr/local/bin/runecode

# Default config ships sandbox_root="" → confined to /workspace (the cwd).
USER runecode
WORKDIR /workspace
ENTRYPOINT ["runecode"]
