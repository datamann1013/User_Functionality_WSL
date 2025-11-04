# RuneGuard Security Service Dockerfile
FROM runecore/python-alpine-dev:latest

WORKDIR /app

# Install minimal runtime dependencies
RUN apk add --no-cache curl

# Install Python dependencies (copy requirements first to leverage Docker layer caching)
# The build context is the project root (this directory), so use relative paths
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

# Copy service source files
COPY . /app/

# Create logs directory with permissive permissions for containerized dev use
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Create non-root user and set ownership
RUN addgroup -g 1001 -S appuser && adduser -S -u 1001 -G appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5001

# Start ErrorLogger service
CMD ["python", "error_server.py"]
