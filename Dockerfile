# Web + API en una sola imagen: Flask sirve el frontend compilado y la API desde el mismo dominio.
# Contexto de build: esta carpeta. Los datos viven en PostgreSQL (servicio `db` de docker-compose.yml); data/*.json solo se
# copia como origen de la migracion inicial y respaldo.
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend .
# VITE_API_URL=/ -> la web llama a /api en su propio dominio; VITE_DEMO vacio = sin aviso de pruebas.
ARG VITE_DEMO=1
ENV VITE_API_URL=/ VITE_DEMO=$VITE_DEMO
RUN npm run build

# --- API (sin frontend): lo que usa docker-compose para el servicio `api` y el contenedor de migracion -------------------
FROM python:3.12-slim AS api

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt gunicorn

RUN useradd --system --no-create-home app
COPY --chown=app backend backend
COPY --chown=app database database
COPY --chown=app data data

USER app
WORKDIR /app/backend
EXPOSE 8000

# Las sesiones viven en PostgreSQL (tabla sesiones), asi que se puede escalar a varios workers.
# SECRET_KEY es obligatoria: el default de config.py permitiria falsificar tokens.
CMD ["sh", "-c", ": \"${SECRET_KEY:?defina SECRET_KEY}\"; exec gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 4 --no-control-socket app:app"]

# --- Web + API en una sola imagen (despliegue de produccion: Flask sirve el frontend compilado) ------------------------
FROM api AS full
COPY --from=web /web/dist /app/web
ENV STATIC_DIR=/app/web
