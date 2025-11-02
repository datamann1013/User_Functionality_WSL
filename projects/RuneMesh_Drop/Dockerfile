FROM rust:1.83-slim-bullseye as builder
WORKDIR /app
# Copy only Cargo.toml (Cargo.lock may not exist in this workspace)
COPY Cargo.toml ./
# Copy source
COPY src ./src
RUN apt-get update && apt-get install -y pkg-config libssl-dev build-essential ca-certificates && rm -rf /var/lib/apt/lists/*
# Build release
RUN cargo build --release

FROM debian:bullseye-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/runedrop ./runedrop
# copy frontend static files into final image so server can serve them
COPY frontend ./frontend
RUN mkdir -p /app/storage/uploads
EXPOSE 5010
CMD ["/app/runedrop"]
