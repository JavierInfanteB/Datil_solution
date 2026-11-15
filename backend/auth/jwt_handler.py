"""Emision y validacion de tokens JWT con expiracion por inactividad.

El JWT en si es stateless, pero la regla de negocio "10 minutos desde la ultima accion" requiere recordar cuando fue la
ultima actividad de cada sesion. Ese registro vive en PostgreSQL (tabla sesiones: jti, IP, dispositivo, ultima_actividad,
cerrada_en), no en memoria: sobrevive a reinicios y a varios workers, y permite cerrar sesiones.
"""
import uuid
from datetime import datetime, timezone

import jwt
from flask import has_request_context, request

from config import Config
from db import accounts as repo


def create_token(user_id, username, role):
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())

    payload = {
        "sub": str(user_id),  # PyJWT >= 2.10 exige texto
        "username": username,
        "role": role,
        "jti": jti,
        "iat": now,
        "exp": now + Config.TOKEN_MAX_AGE,
    }

    token = jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")
    ip = request.remote_addr if has_request_context() else None
    device = request.headers.get("User-Agent") if has_request_context() else None
    repo.session_create(jti, user_id, ip, device)
    return token


def decode_token(token):
    return jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])


def touch_session(jti):
    """Marca la sesion como activa ahora mismo (reinicia el contador de 10 min)."""
    repo.session_touch(jti)


def _elapsed(jti):
    last = repo.session_last_activity(jti)
    return None if last is None else datetime.now(timezone.utc) - last


def is_session_active(jti):
    elapsed = _elapsed(jti)
    return elapsed is not None and elapsed <= Config.SESSION_TIMEOUT


def seconds_until_timeout(jti):
    elapsed = _elapsed(jti)
    if elapsed is None:
        return 0
    return max(0, int((Config.SESSION_TIMEOUT - elapsed).total_seconds()))


def end_session(jti):
    repo.session_end(jti)
