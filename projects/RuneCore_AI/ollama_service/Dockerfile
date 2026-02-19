FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

ENV OLLAMA_HOST=http://ollama:11434
ENV PORT=5002

EXPOSE 5002

ENV GUNICORN_TIMEOUT=300
ENV OLLAMA_REQUEST_TIMEOUT=280
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5002", "--timeout", "300", "ollama_api:app"]
