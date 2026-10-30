"""Alta de usuarios y asignacion de rol, puesto y consultor (solo admin)."""
import re

from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from utils.accounts import ROLES, load_puestos
from utils.data_store import read_json, write_json
from utils.decorators import require_auth, require_role

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

USERNAME = re.compile(r"^[a-z0-9_.-]{3,32}$")
MIN_PASSWORD = 8
PUBLIC_FIELDS = ("id", "username", "name", "role", "puesto", "consultant")


def _public(user):
    return {field: user.get(field) for field in PUBLIC_FIELDS}


def _assign(users, user, body):
    """Aplica el puesto y el consultor de `body` a `user`. Devuelve un mensaje de error o None."""
    if "puesto" in body:
        puesto = body["puesto"] or None
        if puesto is not None and puesto not in load_puestos():
            return "El puesto no existe"
        user["puesto"] = puesto

    if "consultant" in body:
        consultant = body["consultant"] or None
        if consultant is not None:
            boss = next((u for u in users if u["username"] == consultant), None)
            if user["role"] != "usuario" or boss is None or boss["role"] != "consultor":
                return "Solo un usuario puede asignarse, y a un consultor que exista"
        user["consultant"] = consultant
    return None


@users_bp.route("", methods=["GET"])
@require_auth
@require_role("admin")
def list_users():
    return jsonify({"users": [_public(u) for u in read_json("users.json")["users"]], "roles": ROLES})


@users_bp.route("", methods=["POST"])
@require_auth
@require_role("admin")
def create_user():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip().lower()
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""
    role = body.get("role") or "usuario"

    if not USERNAME.match(username) or not name:
        return jsonify({"error": "Usuario (3 a 32 letras minúsculas, números, . _ -) y nombre son requeridos"}), 400
    if len(password) < MIN_PASSWORD:
        return jsonify({"error": f"La contraseña necesita al menos {MIN_PASSWORD} caracteres"}), 400
    if role not in ROLES:
        return jsonify({"error": "Rol inválido"}), 400

    data = read_json("users.json")
    if any(u["username"] == username for u in data["users"]):
        return jsonify({"error": "Ese usuario ya existe"}), 409

    user = {
        "id": max((u["id"] for u in data["users"]), default=0) + 1,
        "username": username,
        "password_hash": generate_password_hash(password),
        "name": name,
        "role": role,
    }
    error = _assign(data["users"], user, body)
    if error:
        return jsonify({"error": error}), 400

    data["users"].append(user)
    write_json("users.json", data)
    return jsonify(_public(user)), 201


@users_bp.route("/<username>", methods=["PATCH"])
@require_auth
@require_role("admin")
def update_user(username):
    body = request.get_json(silent=True) or {}
    data = read_json("users.json")
    users = data["users"]
    user = next((u for u in users if u["username"] == username), None)
    if user is None:
        return jsonify({"error": "El usuario no existe"}), 404

    new_role = body.get("role", user["role"])
    if new_role not in ROLES:
        return jsonify({"error": "Rol inválido"}), 400
    if new_role != user["role"]:
        if username == g.current_user["username"]:
            return jsonify({"error": "No puedes cambiar tu propio rol"}), 400
        user["role"] = new_role
        # Un cliente deja de serlo si cambia de rol, y un consultor que deja de serlo suelta a sus clientes.
        if new_role != "usuario":
            user.pop("consultant", None)
        if new_role != "consultor":
            for other in users:
                if other.get("consultant") == username:
                    other.pop("consultant")

    error = _assign(users, user, body)
    if error:
        return jsonify({"error": error}), 400

    write_json("users.json", data)
    return jsonify(_public(user))
