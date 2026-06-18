FROM python:3.11-slim

# curl is used by the compose healthcheck against /health
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build context is the repo root (see docker-compose.dev.yml) so we can pull in
# the shared CoreClient used for Core registration.
COPY projects/RuneGuard_Insight/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY projects/RuneGuard_Insight/insight.py .
COPY projects/RuneGuard_Insight/error_codes.py .
COPY projects/shared_utils/ /app/shared_utils/

CMD ["python", "-u", "insight.py"]
