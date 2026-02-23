# =============================================================================
# FE-Analyst Dashboard — Multi-stage Docker build
# Stage 1: Build React frontend
# Stage 2: Python runtime serving FastAPI + static React build
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build React frontend
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /build

# Copy package files first for better layer caching
COPY dashboard/frontend/package.json dashboard/frontend/package-lock.json ./

RUN npm ci --no-audit --no-fund

# Copy frontend source and build
COPY dashboard/frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Python runtime with FastAPI
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install minimal system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY dashboard/api/requirements.txt /app/dashboard/api/requirements.txt
RUN pip install --no-cache-dir -r /app/dashboard/api/requirements.txt

# Copy project structure (preserves relative paths for PROJECT_ROOT)
COPY configs/ /app/configs/

# Reports directory — may be empty on first CI build; create stub so server doesn't crash
RUN mkdir -p /app/reports/output
COPY reports/output/ /app/reports/output/

# Analysis engines (src/) — needed by run_analysis.py subprocess
COPY src/ /app/src/

# Dashboard API source
COPY dashboard/api/server.py /app/dashboard/api/server.py
COPY dashboard/api/telegram_bot.py /app/dashboard/api/telegram_bot.py
COPY dashboard/api/seed_portfolio.py /app/dashboard/api/seed_portfolio.py
COPY dashboard/api/run_analysis.py /app/dashboard/api/run_analysis.py

# Seed portfolio DB at build time (bakes holdings into image)
RUN python /app/dashboard/api/seed_portfolio.py

# Copy React build output → static directory served by FastAPI
COPY --from=frontend-builder /build/dist/ /app/dashboard/api/static/

# Cloud Run injects PORT env var (default 8080)
ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

CMD ["sh", "-c", "python -m uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080} --app-dir /app/dashboard/api --timeout-keep-alive 120"]
