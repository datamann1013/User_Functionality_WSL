FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
# Copy project files
COPY . /app

# Ensure top-level migrate script is available at /app/migrate.py for in-container migrations
# (some CI/exec commands expect /app/migrate.py)
COPY migrate.py /app/migrate.py

# Small wrapper to run migrations or start the server
COPY start_core_memory.sh /app/start_core_memory.sh
RUN chmod +x /app/start_core_memory.sh
ENV PYTHONUNBUFFERED=1
CMD ["/app/start_core_memory.sh"]
