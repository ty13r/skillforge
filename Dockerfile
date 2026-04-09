# SkillForge Dockerfile
# Multi-stage: build the Vite frontend, then the Python runtime serves both
# the FastAPI backend and the SPA from frontend/dist via the optional mount
# in skillforge/main.py.

# ---- Stage 1: build the frontend ------------------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime ---------------------------------------------
FROM python:3.12-slim AS runtime

# uv is the fastest pip; install it once at the OS level so we can run
# `uv sync` against the project.
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy project metadata first so dependency layer caches independently
# from source changes.
COPY pyproject.toml uv.lock README.md ./
COPY skillforge/ ./skillforge/

# Install dependencies (production only — no dev extras).
# Reduce uv's default parallelism so the build survives Railway's memory
# ceiling: the claude-agent-sdk wheel alone is 68 MB, and uv's default
# parallel downloads + link step peaks over the build-container RAM limit
# and gets OOM-killed (exit 137). `UV_CONCURRENT_*=1` serializes the work.
ENV UV_CONCURRENT_DOWNLOADS=1
ENV UV_CONCURRENT_INSTALLS=1
ENV UV_COMPILE_BYTECODE=0
ENV UV_LINK_MODE=copy
ENV UV_NO_CACHE=1
RUN uv sync --frozen --no-dev

# Copy the rest of the project: docs (golden template + research), bible,
# the built frontend dist from stage 1.
COPY docs/ ./docs/
COPY bible/ ./bible/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Railway sets $PORT dynamically; default to 8000 for local docker run.
ENV PORT=8000
EXPOSE 8000

# Use `sh -c` so $PORT is expanded at runtime, not at build time.
CMD ["sh", "-c", "uv run uvicorn skillforge.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
