FROM python:3.11-slim
LABEL maintainer="runecore-dev"

# Use noninteractive frontend
ENV DEBIAN_FRONTEND=noninteractive

# Try multiple Debian mirrors and force IPv4 during update/install to avoid single-mirror failures.
RUN set -eux; \
        # Create a reliable sources.list using mirrors that respond from this environment.
            printf '%s\n' \
                'deb http://ftp.us.debian.org/debian stable main contrib non-free' \
                'deb http://ftp.uk.debian.org/debian stable main contrib non-free' \
                'deb http://mirror.math.princeton.edu/pub/debian stable main contrib non-free' \
                '' \
                'deb http://ftp.us.debian.org/debian-security stable-security main contrib non-free' \
                'deb http://ftp.uk.debian.org/debian-security stable-security main contrib non-free' \
                > /etc/apt/sources.list
        # Force IPv4 and try update/install (retries help transient network issues)
        for i in 1 2 3; do \
            if apt-get update -o Acquire::ForceIPv4=true && apt-get install -y --no-install-recommends \
                     build-essential gcc libpq-dev curl; then \
                break; \
            else \
                echo "apt-get attempt $i failed, retrying..."; sleep 2; \
            fi; \
        done; \
        rm -rf /var/lib/apt/lists/*

# Create a non-root dev user
RUN useradd -ms /bin/bash dev
USER dev
WORKDIR /home/dev

CMD ["/bin/bash"]
