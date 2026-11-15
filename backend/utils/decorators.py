"""Decoradores reutilizables para autenticacion y permisos por modulo."""
from functools import wraps

import jwt as pyjwt
from flask import g, jsonify, request

from auth.jwt_handler import decode_token, is_session_active, touch_session
from utils import audit
from utils.accounts import effective_permissions, find_user


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
            return jsonify({"error": "Token inválido"}), 401

        if not is_session_active(payload["jti"]):
            return jsonify({"error": "Sesión expirada por inactividad"}), 401

        # El rol y el puesto salen de la base de datos, no del token: cambiarlos o dar de baja a
        # alguien surte efecto en su siguiente peticion, sin esperar a que venza su sesion.
        record = find_user(id=int(payload["sub"]))
        if record is None or record.get("disabled"):
            return jsonify({"error": "Usuario no encontrado"}), 401

        touch_session(payload["jti"])
        g.current_user = {
            "id": record["id"],
            "username": record["username"],
            "name": record["name"],
            "role": record["role"],
            "puesto": record.get("puesto"),
            "jti": payload["jti"],
        }
        return f(*args, **kwargs)

    return wrapper


def acting_username():
    """(usuario, error): la cartera sobre la que opera la peticion.

    Un usuario opera la suya. El admin no tiene cartera propia: opera solo en nombre de un cliente
    (parametro `client` en la URL o en el cuerpo) y sin cliente valido se le rechaza.
    """
    user = g.current_user
    if user["role"] != "admin":
        return user["username"], None
    target = request.args.get("client") or (request.get_json(silent=True) or {}).get("client")
    client = find_user(username=target) if target else None
    if client is None or client["role"] != "usuario":
        return None, (jsonify({"error": "El administrador opera solo en nombre de un cliente"}), 403)
    return client["username"], None


def require_role(*roles):
    """Solo deja pasar a los roles dados. Va despues de require_auth."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if g.current_user["role"] not in roles:
                audit.record_denied(f"rol {g.current_user['role']} no puede usar {request.path}")
                return jsonify({"error": "Permiso denegado"}), 403
            return f(*args, **kwargs)

        return wrapper

    return decorator


def is_granted(granted, perm):
    """'trading' concede el modulo completo y 'trading.bono' solo esa seccion.

    Pedir el modulo ('trading') pasa con cualquiera de sus secciones.
    Misma regla que frontend/src/utils/permissions.js.
    """
    module_id = perm.split(".")[0]
    return module_id in granted or perm in granted or any(p.startswith(perm + ".") for p in granted)


def has_permission(user, perm):
    """El rol admin siempre pasa; el resto se valida contra sus permisos y los de su puesto."""
    if user["role"] == "admin":
        return True
    return is_granted(effective_permissions(user), perm)


def require_permission(perm):
    """Bloquea el acceso si el usuario no tiene el modulo (o seccion) habilitado."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                return jsonify({"error": "No autenticado"}), 401

            if not has_permission(user, perm):
                audit.record_denied(f"falta el permiso {perm} en {request.path}")
                return jsonify({"error": "Permiso denegado"}), 403

            return f(*args, **kwargs)

        return wrapper

    return decorator
