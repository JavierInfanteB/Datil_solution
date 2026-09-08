"""Decoradores reutilizables para autenticacion y permisos por modulo."""
from functools import wraps

import jwt as pyjwt
from flask import g, jsonify, request

from auth.jwt_handler import decode_token, is_session_active, touch_session
from utils.data_store import read_json


def require_auth(f):
    """Valida el JWT y que la sesion siga activa (10 min desde la ultima accion)."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Token requerido"}), 401

        token = auth_header.split(" ", 1)[1]
        try:
            payload = decode_token(token)
        except pyjwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except pyjwt.InvalidTokenError:
            return jsonify({"error": "Token invalido"}), 401

        if not is_session_active(payload["jti"]):
            return jsonify({"error": "Sesion expirada por inactividad"}), 401

        touch_session(payload["jti"])
        g.current_user = {
            "id": payload["sub"],
            "username": payload["username"],
            "role": payload["role"],
            "jti": payload["jti"],
        }
        return f(*args, **kwargs)

    return wrapper


def require_permission(module_id):
    """Bloquea el acceso si el usuario no tiene el modulo habilitado.

    El rol admin siempre pasa; el resto se valida contra permissions.json.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                return jsonify({"error": "No autenticado"}), 401

            if user["role"] == "admin":
                return f(*args, **kwargs)

            permissions = read_json("permissions.json")
            if module_id not in permissions.get(user["username"], []):
                return jsonify({"error": "Permiso denegado"}), 403

            return f(*args, **kwargs)

        return wrapper

    return decorator
