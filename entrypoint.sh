#!/bin/sh
# ─── VoiceMarket Docker Entrypoint ────────────────────────────────────────────
# Waits for services, runs migrations, then starts the application.
set -e

echo "=========================================="
echo "  AI Voice Data Marketplace — Starting Up"
echo "=========================================="

# ─── Wait for PostgreSQL ──────────────────────────────────────
echo "⏳ Waiting for PostgreSQL at db:5432..."
while ! nc -z db 5432; do
  sleep 1
done
echo "✅ PostgreSQL is ready"

# ─── Wait for Redis ────────────────────────────────────────────
echo "⏳ Waiting for Redis at redis:6379..."
while ! nc -z redis 6379; do
  sleep 1
done
echo "✅ Redis is ready"

# ─── Run migrations ────────────────────────────────────────────
echo "🔄 Running database migrations..."
python manage.py migrate --noinput

# ─── Collect static files ──────────────────────────────────────
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear 2>/dev/null || true

echo "🚀 Starting Daphne ASGI server..."
exec "$@"
