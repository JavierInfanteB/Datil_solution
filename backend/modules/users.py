"""Alta de usuarios, cambio de contrasena y nombre, suspension y asignacion de rol, puesto y consultor (solo admin)."""
import re

from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from db import accounts as repo
from db import connection as c
from db import portfolio as portfolio_repo
from utils import notifications
from utils.accounts import ROLES, load_puestos
from utils.decorators import require_auth, require_role

users_bp = Blueprint("users", __name__, url_prefix="/api/users")

USERNAME = re.compile(r"^[a-z0-9_.-]{3,32}$")
MIN_PASSWORD = 8
MAX_NAME = 120  # usuarios.nombre es VARCHAR(120)
PUBLIC_FIELDS = ("id", "username", "name", "role", "puesto", "consultant", "disabled", "deleted")


def _public(user):
    return {field: user.get(field) for field in PUBLIC_FIELDS}


def _check_assignment(users, user, body, role=None):
    """Valida el puesto y el consultor de `body` para `user`. Devuelve un mensaje de error o None."""
    if "puesto" in body:
        puesto = body["puesto"] or None
        if puesto is not None and puesto not in load_puestos():
            return "El puesto no existe"

    if "consultant" in body:
        consultant = body["consultant"] or None
        if consultant is not None:
            boss = next((u for u in users if u["username"] == consultant), None)
            if (role or user["role"]) != "usuario" or boss is None or boss["role"] != "consultor":
                return "Solo un usuario puede asignarse, y a un consultor que exista"
    return None


def _apply_assignment(username, body):
    if "puesto" in body:
        repo.set_puesto(username, body["puesto"] or None)
    if "consultant" in body:
        repo.set_consultant(username, body["consultant"] or None, g.current_user["id"])


@users_bp.route("", methods=["GET"])
@require_auth
@require_role("admin")
def list_users():
    return jsonify({"users": [_public(u) for u in repo.list_users()], "roles": ROLES})


@users_bp.route("", methods=["POST"])
@require_auth
@require_role("admin")
def create_user():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip().lower()
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""
    role = body.get("role") or "usuario"

    if not USERNAME.match(username) or not name or len(name) > MAX_NAME:
        return jsonify({"error": "Usuario (3 a 32 letras minúsculas, números, . _ -) y nombre son requeridos"}), 400
    if len(password) < MIN_PASSWORD:
        return jsonify({"error": f"La contraseña necesita al menos {MIN_PASSWORD} caracteres"}), 400
    if role not in ROLES:
        return jsonify({"error": "Rol inválido"}), 400

    users = repo.list_users()
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Ese usuario ya existe"}), 409

    error = _check_assignment(users, {"role": role}, body)
    if error:
        return jsonify({"error": error}), 400

    try:
        with c.transaction():
            repo.create_user(username, name, generate_password_hash(password), role, created_by=g.current_user["id"])
            _apply_assignment(username, body)
    except repo.UserExists:
        return jsonify({"error": "Ese usuario ya existe"}), 409
    return jsonify(_public(repo.get_user(username=username))), 201


@users_bp.route("/<username>", methods=["PATCH"])
@require_auth
@require_role("admin")
def update_user(username):
    body = request.get_json(silent=True) or {}
    users = repo.list_users()
    user = next((u for u in users if u["username"] == username), None)
    if user is None:
        return jsonify({"error": "El usuario no existe"}), 404

    # Primero se valida todo: si algo falla no se guarda nada.
    if "password" in body and len(body["password"] or "") < MIN_PASSWORD:
        return jsonify({"error": f"La contraseña necesita al menos {MIN_PASSWORD} caracteres"}), 400
    if "name" in body and (not (body["name"] or "").strip() or len(body["name"].strip()) > MAX_NAME):
        return jsonify({"error": "El nombre no puede quedar vacío ni pasar de 120 caracteres"}), 400
    if "disabled" in body and username == g.current_user["username"]:
        return jsonify({"error": "No puedes suspender tu propia cuenta"}), 400
    new_role = body.get("role", user["role"])
    if new_role not in ROLES:
        return jsonify({"error": "Rol inválido"}), 400
    if new_role != user["role"] and username == g.current_user["username"]:
        return jsonify({"error": "No puedes cambiar tu propio rol"}), 400
    error = _check_assignment(users, user, body, role=new_role)
    if error:
        return jsonify({"error": error}), 400

    with c.transaction():
        if "password" in body:
            repo.set_password(username, generate_password_hash(body["password"]))
        if "name" in body:
            repo.set_name(username, body["name"].strip())
        if "disabled" in body:
            reactivated = user["disabled"] and not body["disabled"]
            if reactivated:  # volver a activar tambien levanta al usuario dado de baja
                repo.set_state(username, "activo")
                notifications.add(username, g.current_user, "aviso", "Tu cuenta fue reactivada",
                                  "Tu cuenta de Datil Solution volvió a estar activa." + (" Tu cartera empieza en cero." if user["deleted"] else ""))
            elif body["disabled"] and not user["disabled"]:
                repo.set_state(username, "suspendido")
        if new_role != user["role"]:
            # Un cliente deja de serlo si cambia de rol, y un consultor que deja de serlo suelta a sus clientes.
            if new_role != "usuario":
                repo.set_consultant(username, None)
            if new_role != "consultor":
                repo.release_clients_of(username)
            repo.set_role(username, new_role)
        _apply_assignment(username, body)
    return jsonify(_public(repo.get_user(username=username)))


def _balance(username):
    """Efectivo, posiciones y ordenes pendientes de un usuario: lo que le queda dentro de Datil."""
    return portfolio_repo.balance_summary(username)


@users_bp.route("/<username>", methods=["DELETE"])
@require_auth
@require_role("admin")
def delete_user(username):
    """Dar de baja: en realidad suspende la cuenta, y solo si no tiene dinero, posiciones ni ordenes pendientes.
    Reactivarla (PATCH disabled=false) la levanta de nuevo y le avisa al usuario."""
    user = repo.get_user(username=username)
    if user is None:
        return jsonify({"error": "El usuario no existe"}), 404
    if username == g.current_user["username"]:
        return jsonify({"error": "No puedes darte de baja a ti mismo"}), 400
    cash, holdings, pending = _balance(username)
    if abs(cash) >= 0.005 or holdings or pending:
        return jsonify({"error": "Solo se da de baja a quien está en cero: sin efectivo, posiciones ni órdenes pendientes"}), 409

    repo.set_state(username, "baja")
    return jsonify(_public(repo.get_user(username=username)))
