FROM python:3.11-slim

WORKDIR /app

# Install minimal deps
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
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5002", "ollama_api_optimized:app"]
