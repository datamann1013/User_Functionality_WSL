FROM rust:1.73-slim-bullseye as builder
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN apt-get update && apt-get install -y pkg-config libssl-dev build-essential ca-certificates && rm -rf /var/lib/apt/lists/*
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/runedrop ./runedrop
RUN mkdir -p /app/storage/uploads
EXPOSE 5010
CMD ["/app/runedrop"]
