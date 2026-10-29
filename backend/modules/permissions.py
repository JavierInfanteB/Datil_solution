"""Gestion de permisos: que modulos puede ver cada usuario no-admin."""
from flask import Blueprint, g, jsonify, request

from utils.data_store import read_json, write_json
from utils.decorators import require_auth

permissions_bp = Blueprint("permissions", __name__, url_prefix="/api/permissions")

# Catalogo fijo de modulos instalados en el index y sus secciones (las
# subpestañas del menu lateral). Agregar un modulo o seccion aqui es lo unico
# que se necesita para que el admin pueda concederlo. Un permiso es el id del
# modulo ("trading" = completo) o "modulo.seccion" ("trading.bono" = solo esa).
MODULES = {
    "portfolio": [],
    "trading": ["accion", "bono"],
    "risk": [],
    "permissions": [],
}
AVAILABLE_PERMISSIONS = set(MODULES) | {f"{m}.{s}" for m, sections in MODULES.items() for s in sections}


@permissions_bp.route("/me", methods=["GET"])
@require_auth
def get_my_permissions():
    if g.current_user["role"] == "admin":
        return jsonify({"modules": list(MODULES)})

    permissions = read_json("permissions.json")
    return jsonify({"modules": permissions.get(g.current_user["username"], [])})


@permissions_bp.route("", methods=["GET"])
@require_auth
def get_all_permissions():
    if g.current_user["role"] != "admin":
        return jsonify({"error": "Permiso denegado"}), 403

    # Lista y no dict: jsonify ordena las llaves y perderia el orden del catalogo.
    return jsonify({
        "modules": [{"id": m, "sections": sections} for m, sections in MODULES.items()],
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

    valid_modules = [m for m in modules if m in AVAILABLE_PERMISSIONS]
    permissions = read_json("permissions.json")
    permissions[username] = valid_modules
    write_json("permissions.json", permissions)

    return jsonify({"username": username, "modules": valid_modules})
