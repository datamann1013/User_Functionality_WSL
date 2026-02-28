FROM runecore/rust-builder-dev:latest as builder
WORKDIR /app
# Install newer Rust with edition2024 support
RUN apt-get update && apt-get install -y pkg-config libssl-dev build-essential ca-certificates curl && rm -rf /var/lib/apt/lists/*
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain nightly
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy Cargo.toml and source
COPY Cargo.toml ./
COPY src ./src

# Build release
RUN cargo build --release

FROM debian:bullseye-slim
RUN apt-get update && apt-get install -y ca-certificates curl && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/target/release/runedrop ./runedrop

# Build frontend
COPY frontend/package.json ./frontend/
COPY frontend/vite.config.js ./frontend/
COPY frontend/index.html ./frontend/
COPY frontend/src ./frontend/src

WORKDIR /app/frontend
RUN npm install && npm run build

# Move dist to expected location at root level
WORKDIR /app
RUN mv frontend/dist ./frontend-dist

# Create storage directory
RUN mkdir -p /app/storage/uploads

EXPOSE 5010
CMD ["/app/runedrop"]
