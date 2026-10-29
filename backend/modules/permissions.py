"""Gestion de permisos: que modulos puede ver cada usuario no-admin."""
from flask import Blueprint, g, jsonify, request

from utils.data_store import read_json, write_json
from utils.decorators import require_auth

permissions_bp = Blueprint("permissions", __name__, url_prefix="/api/permissions")

# Catalogo fijo de modulos instalados en el index. Agregar uno nuevo aqui
# es lo unico que se necesita para que el admin pueda concederlo.
AVAILABLE_MODULES = ["portfolio", "trading", "risk", "permissions"]


@permissions_bp.route("/me", methods=["GET"])
@require_auth
def get_my_permissions():
    if g.current_user["role"] == "admin":
        return jsonify({"modules": AVAILABLE_MODULES})

    permissions = read_json("permissions.json")
    return jsonify({"modules": permissions.get(g.current_user["username"], [])})


@permissions_bp.route("", methods=["GET"])
@require_auth
def get_all_permissions():
    if g.current_user["role"] != "admin":
        return jsonify({"error": "Permiso denegado"}), 403

    return jsonify({
        "available_modules": AVAILABLE_MODULES,
        "permissions": read_json("permissions.json"),
    })


@permissions_bp.route("/<username>", methods=["PUT"])
@require_auth
def update_permissions(username):
    if g.current_user["role"] != "admin":
        return jsonify({"error": "Permiso denegado"}), 403

    body = request.get_json(silent=True) or {}
    modules = body.get("modules", [])
    if not isinstance(modules, list):
        return jsonify({"error": "modules debe ser una lista"}), 400

    valid_modules = [m for m in modules if m in AVAILABLE_MODULES]
    permissions = read_json("permissions.json")
    permissions[username] = valid_modules
    write_json("permissions.json", permissions)

    return jsonify({"username": username, "modules": valid_modules})
