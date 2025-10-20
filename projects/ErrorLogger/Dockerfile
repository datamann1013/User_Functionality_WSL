# RuneGuard Security Service Dockerfile
FROM python:3.11-alpine

WORKDIR /app

# Install minimal dependencies
RUN apk add --no-cache curl

# Copy requirements and install dependencies
COPY projects/ErrorLogger/requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

# Copy ErrorLogger code
COPY projects/ErrorLogger/ /app/

# Create logs directory
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Create non-root user
RUN addgroup -g 1001 -S appuser && adduser -S -u 1001 -G appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=60s --timeout=3s --start-period=15s --retries=2 \
    CMD curl -f http://localhost:5001/health || exit 1

EXPOSE 5001

# Start ErrorLogger service
CMD ["python", "error_server.py"]
