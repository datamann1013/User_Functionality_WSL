FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn", "core_memory.app:app", "--host", "0.0.0.0", "--port", "5010"]
