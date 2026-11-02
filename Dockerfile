# Root Dockerfile: FastAPI backend + built React UI.
# Distinct from sandbox/Dockerfile.sandbox, the isolated image generated code runs in.

# Stage 1: build the React frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# Stage 2: just the docker CLI binary (no daemon) to talk to the socket proxy
FROM docker:27-cli AS docker-cli

# Stage 3: runtime
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 agent \
    && mkdir -p /data \
    && chown agent:agent /data

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY eval/ ./eval/
RUN pip install --no-cache-dir .

COPY scripts/ ./scripts/
COPY results/ ./results/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1 \
    DB_PATH=/data/agent.db \
    MEMORY_DIR=/data/memory_db \
    DEMO_MODE=false

USER agent
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
