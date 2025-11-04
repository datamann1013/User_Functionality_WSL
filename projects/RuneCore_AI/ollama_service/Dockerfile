FROM runecore/python-slim-dev:latest

WORKDIR /app

# Install minimal deps
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV OLLAMA_HOST=http://ollama:11434
ENV PORT=5002

EXPOSE 5002

# Run Gunicorn with 4 workers serving the Flask app (module: app)
ENV GUNICORN_TIMEOUT=300
ENV OLLAMA_REQUEST_TIMEOUT=280
# Use a literal timeout value in the CMD to avoid JSON string interpolation issues
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5002", "--timeout", "300", "ollama_api_optimized:app"]

