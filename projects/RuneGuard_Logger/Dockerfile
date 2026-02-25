# RuneGuard Security Service Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (copy requirements first to leverage Docker layer caching)
# The build context is the project root (this directory), so use relative paths
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

# Copy service source files
COPY . /app/

# Create logs directory with permissive permissions for containerized dev use
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Create non-root user and set ownership
RUN groupadd -g 1001 appuser && useradd -u 1001 -g appuser -s /bin/bash -M appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5001

# Start ErrorLogger service
CMD ["python", "error_server.py"]
