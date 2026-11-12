# ==============================================================================
# MIICiQ — Enterprise Knowledge Assistant Dockerfile
# Python 3.12/3.14 on-premise container
# ==============================================================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies for document parsing and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application codebase
COPY . /app/

# Non-root runtime user; data directories are mounted as volumes at runtime
RUN useradd --create-home --uid 1000 miiciq \
    && mkdir -p /app/media /app/staticfiles /app/chroma_db /app/db_volume /app/sample_documents \
    && chown -R miiciq:miiciq /app

USER miiciq

# Static files are collected at container start (see docker-compose.yml). Migrations also run at start,
# never at build time, so no database is baked into the image.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz/ || exit 1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "4", "--timeout", "180"]
