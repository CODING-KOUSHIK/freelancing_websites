# ─── Build stage ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Only need pip + wheel — no gcc/build-essential needed because
# requirements use pre-built binaries (psycopg2-binary, etc.)
COPY requirements.txt .
RUN pip install --upgrade pip --quiet \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt --quiet


# ─── Runtime stage ─────────────────────────────────────────────
FROM python:3.12-slim

LABEL maintainer="VoiceMarket <koushikbiswas029@gmail.com>"
LABEL description="AI Voice Data Marketplace — Django/Daphne ASGI server"

# Minimal runtime deps — libpq5 for postgres client, curl for healthcheck, nc for wait scripts
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install wheels from builder (no internet, no compilation)
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels /wheels/* --quiet \
    && rm -rf /wheels

# Copy source code
COPY . .

# Create required directories and set permissions
RUN mkdir -p /app/media /app/staticfiles /app/logs \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Default: Daphne ASGI — handles HTTP + WebSockets
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
