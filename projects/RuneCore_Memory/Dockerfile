FROM runecore/python-slim-dev:latest
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
COPY manage_migrations.sh /app/manage_migrations.sh
USER root
RUN chmod +x /app/start_core_memory.sh
RUN chmod +x /app/manage_migrations.sh
# Ensure files owned by non-root dev user if base image provides one
RUN if id dev >/dev/null 2>&1; then chown -R dev:dev /app || true; fi
USER dev
ENV PYTHONUNBUFFERED=1
CMD ["/app/start_core_memory.sh"]
