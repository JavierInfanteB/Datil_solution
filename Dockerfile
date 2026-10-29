# Web + API en una sola imagen: Flask sirve el frontend compilado y la API desde el mismo dominio.
# Contexto de build: esta carpeta, porque config.py lee ../data (montar un volumen en /app/data para que sobreviva).
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend .
# VITE_API_URL=/ -> la web llama a /api en su propio dominio; VITE_DEMO vacio = sin aviso de pruebas.
ARG VITE_DEMO=1
ENV VITE_API_URL=/ VITE_DEMO=$VITE_DEMO
RUN npm run build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt gunicorn

RUN useradd --system --no-create-home app
COPY --chown=app backend backend
COPY --chown=app data data
COPY --from=web /web/dist /app/web
ENV STATIC_DIR=/app/web

USER app
WORKDIR /app/backend
EXPOSE 8000

# 1 worker: las sesiones viven en memoria y el JSON se protege con un lock de proceso.
# SECRET_KEY es obligatoria: el default de config.py permitiria falsificar tokens.
CMD ["sh", "-c", ": \"${SECRET_KEY:?defina SECRET_KEY}\"; exec gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --no-control-socket app:app"]
