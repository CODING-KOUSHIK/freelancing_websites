FROM python:3.12-slim

LABEL maintainer="VoiceMarket"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Directories
RUN mkdir -p /app/media /app/staticfiles /app/logs

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

# Railway uses dynamic PORT; default 8000 for local Docker
ENV PORT=8000
EXPOSE 8000

CMD ["/app/entrypoint.sh"]
