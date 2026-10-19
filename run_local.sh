#!/usr/bin/env bash
# ==============================================================================
# MIICiQ — Quick Local Launch Script
# ==============================================================================
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "  🚀 Starting MIICiQ — Internal Knowledge Assistant"
echo "=========================================================="

if [ -f "./venv/bin/activate" ]; then
    source ./venv/bin/activate
fi

# Apply migrations
python manage.py migrate

# Seed sample documents if none exist
DOC_COUNT=$(python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from assistant.models import Document; print(Document.objects.count())")
if [ "$DOC_COUNT" -eq "0" ]; then
    echo "No documents detected. Seeding sample company SOPs..."
    python manage.py ingest_samples
fi

echo "=========================================================="
echo "  🌐 Server running at: http://127.0.0.1:8000/"
echo "  💬 Chat Dashboard:   http://127.0.0.1:8000/"
echo "  🔍 Search Mode:      http://127.0.0.1:8000/search/"
echo "  ⚙️ Admin Panel:      http://127.0.0.1:8000/admin-dashboard/"
echo "=========================================================="

exec python manage.py runserver 0.0.0.0:8000
