# syntax=docker/dockerfile:1

# --- Frontend build ---------------------------------------------------------
FROM node:24.22.3-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Runtime: FastAPI serves the API (/api) and the built frontend ----------
FROM python:3.13.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/habits.db \
    FRONTEND_DIST=/app/frontend

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/alembic.ini .
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY --from=frontend /src/dist ./frontend

# /data holds the SQLite database; a named volume inherits these permissions
RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && install -d -o 10001 -g 10001 -m 700 /data

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

# exec: uvicorn becomes PID 1 and receives SIGTERM directly
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.web:application --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS:-*}\""]
