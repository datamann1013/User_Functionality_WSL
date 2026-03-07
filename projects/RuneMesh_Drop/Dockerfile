# ============================================================
# Stage 1: Rust builder
# ============================================================
FROM runecore/rust-builder-dev:latest AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y pkg-config libssl-dev build-essential ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain nightly
ENV PATH="/root/.cargo/bin:${PATH}"

COPY Cargo.toml ./
COPY src ./src

RUN cargo build --release

# ============================================================
# Stage 2: Frontend builder (Node stays here, not in runtime)
# ============================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 3: Runtime — only the binary + built frontend assets
# ============================================================
FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y ca-certificates curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder          /app/target/release/runedrop ./runedrop
COPY --from=frontend-builder /app/frontend/dist           ./frontend-dist

RUN mkdir -p /app/storage/uploads

EXPOSE 5010
CMD ["/app/runedrop"]
