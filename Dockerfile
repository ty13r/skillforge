# SkillForge Dockerfile — placeholder, finalized in Step 11
# Multi-stage: build frontend, then Python runtime serves static + API

FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
COPY skillforge/ ./skillforge/
COPY docs/ ./docs/
COPY bible/ ./bible/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
RUN uv sync --no-dev

ENV PORT=8000
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "skillforge.main:app", "--host", "0.0.0.0", "--port", "8000"]
