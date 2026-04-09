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
# `uv sync --frozen` uses the locked versions from uv.lock.
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
