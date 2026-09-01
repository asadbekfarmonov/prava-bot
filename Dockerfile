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

# Run migrations on startup, then bind Railway's $PORT (never hard-coded).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
