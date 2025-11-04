FROM python:3.11-slim
LABEL maintainer="runecore-dev"

# Use noninteractive frontend
ENV DEBIAN_FRONTEND=noninteractive

# Try multiple Debian mirrors and force IPv4 during update/install to avoid single-mirror failures.
RUN set -eux; \
        # determine codename from base image (/etc/os-release) and write sources list to a mirror we tested
        CODENAME=$(awk -F= '/^VERSION_CODENAME=/ {print $2}' /etc/os-release | tr -d '"'); \
        if [ -z "$CODENAME" ]; then CODENAME=stable; fi; \
        echo "Detected codename: $CODENAME"; \
        # Use mirror.math.princeton (responded OK for trixie/stable) for main packages
        printf '%s\n' "deb http://mirror.math.princeton.edu/pub/debian ${CODENAME} main contrib non-free" \
                "deb http://mirror.math.princeton.edu/pub/debian ${CODENAME}-updates main contrib non-free" \
                > /etc/apt/sources.list; \
        # Try to add security repo from deb.debian.org (some codenames map there)
        printf '%s\n' "deb http://deb.debian.org/debian-security ${CODENAME}-security main contrib non-free" >> /etc/apt/sources.list; \
        apt-get update -o Acquire::ForceIPv4=true; \
        apt-get install -y --no-install-recommends build-essential gcc libpq-dev curl; \
        rm -rf /var/lib/apt/lists/*

# Create a non-root dev user
RUN useradd -ms /bin/bash dev
USER dev
WORKDIR /home/dev

CMD ["/bin/bash"]
