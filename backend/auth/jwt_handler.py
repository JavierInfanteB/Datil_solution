"""Emision y validacion de tokens JWT con expiracion por inactividad.

El JWT en si es stateless, pero la regla de negocio "10 minutos desde la
ultima accion" requiere recordar cuando fue la ultima actividad de cada
sesion. Para eso se mantiene un registro en memoria (jti -> ultima
actividad) que se actualiza en cada peticion autenticada.
"""
import uuid
from datetime import datetime, timezone

import jwt

from config import Config

# jti -> datetime de la ultima actividad registrada.
_active_sessions = {}


def create_token(user_id, username, role):
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())

    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "jti": jti,
        "iat": now,
        "exp": now + Config.TOKEN_MAX_AGE,
    }

    token = jwt.encode(payload, Config.SECRET_KEY, algorithm="HS256")
    _active_sessions[jti] = now
    return token


def decode_token(token):
    return jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])


def touch_session(jti):
    """Marca la sesion como activa ahora mismo (reinicia el contador de 10 min)."""
    _active_sessions[jti] = datetime.now(timezone.utc)


def is_session_active(jti):
    last_activity = _active_sessions.get(jti)
    if last_activity is None:
        return False
    return datetime.now(timezone.utc) - last_activity <= Config.SESSION_TIMEOUT


def seconds_until_timeout(jti):
    last_activity = _active_sessions.get(jti)
    if last_activity is None:
        return 0
    elapsed = datetime.now(timezone.utc) - last_activity
    remaining = Config.SESSION_TIMEOUT - elapsed
    return max(0, int(remaining.total_seconds()))


def end_session(jti):
    _active_sessions.pop(jti, None)
