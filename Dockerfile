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

# Create media, staticfiles, and chroma persistent directories
RUN mkdir -p /app/media /app/staticfiles /app/chroma_db /app/sample_documents

# Run migrations and collect static
RUN python manage.py migrate && python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
