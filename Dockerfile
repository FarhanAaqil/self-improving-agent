# Root Dockerfile — FastAPI backend service container
# Note: Distinct from sandbox/Dockerfile.sandbox (the isolated execution environment)

# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Runtime Environment
FROM python:3.11-slim
WORKDIR /app

# Install docker CLI for sibling-container sandbox management via socket mount
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY app/ ./app/
COPY eval/ ./eval/
COPY scripts/ ./scripts/
COPY results/ ./results/
COPY README.md ./
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000
ENV PYTHONUNBUFFERED=1
ENV DEMO_MODE=false

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
