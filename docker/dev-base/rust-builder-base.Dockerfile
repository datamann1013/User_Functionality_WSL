FROM rust:1.82-slim-bullseye
LABEL maintainer="runecore-dev"

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libssl-dev \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV PATH="/usr/local/cargo/bin:${PATH}"
CMD ["/bin/bash"]
