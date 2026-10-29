# Solo el backend (el frontend va en Cloudflare Pages). Contexto de build: esta carpeta,
# porque config.py lee ../data. Montar un volumen en /app/data para que sobreviva.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt gunicorn

RUN useradd --system --no-create-home app
COPY --chown=app backend backend
COPY --chown=app data data

USER app
WORKDIR /app/backend
EXPOSE 8000

# 1 worker: las sesiones viven en memoria y el JSON se protege con un lock de proceso.
# SECRET_KEY es obligatoria: el default de config.py permitiria falsificar tokens.
CMD ["sh", "-c", ": \"${SECRET_KEY:?defina SECRET_KEY}\"; exec gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --no-control-socket app:app"]
