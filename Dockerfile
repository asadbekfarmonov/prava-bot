# --- Stage 1: build the Vite React Mini App ---
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend ./
RUN npm run build

# --- Stage 2: FastAPI application image ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV APP_DEBUG=false
ENV FRONTEND_DIST_DIR=/app/frontend/dist

WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

# Migration strategy (docs/spec/13 "Database migrations"):
#   v1 SINGLE INSTANCE: run `alembic upgrade head` on startup before serving. Simple and
#   correct for one instance. When scaling to MULTIPLE instances, startup migrations race —
#   move to a dedicated Railway release/pre-deploy step OR guard startup migrations with a
#   Postgres advisory lock so only one instance migrates and the others wait. Not implemented
#   now (single-instance v1); documented so the multi-instance cutover is a config change.
# Then bind Railway's $PORT at runtime (never hard-coded).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
