"""Gestion de permisos: que modulos puede ver cada usuario no-admin, solo o por puesto."""
import re

from flask import Blueprint, g, jsonify, request

from utils.accounts import effective_permissions, find_user, load_puestos, load_users
from utils.data_store import read_json, write_json
from utils.decorators import require_auth, require_role

permissions_bp = Blueprint("permissions", __name__, url_prefix="/api/permissions")

# Catalogo fijo de modulos instalados en el index y sus secciones (las
# subpestañas del menu lateral). Agregar un modulo o seccion aqui es lo unico
# que se necesita para que el admin pueda concederlo. Un permiso es el id del
# modulo ("trading" = completo) o "modulo.seccion" ("trading.bono" = solo esa).
MODULES = {
    "portfolio": [],
    "trading": ["accion", "bono"],
    "risk": [],
    "avisos": [],
    "plan": ["alertas", "metas", "notas", "reporte"],
    "consultor": ["clientes", "sugerencias", "tendencias", "avisos"],
    "clientes": ["resumen", "lista", "tendencias", "avisos"],
    "permissions": [],
}
# Modulos personales de un rol: solo ese rol los usa ("Mis clientes" es del consultor y la bandeja de
# avisos es del usuario). Ni el admin los ve, aunque lo controle todo; el resto de modulos sirve a cualquier rol.
# La cartera y las compras son de los clientes: el admin no tiene cartera propia, opera en nombre de un cliente
# desde su modulo "clientes" (ver acting_username).
ROLE_ONLY = {"consultor": "consultor", "avisos": "usuario", "portfolio": "usuario", "trading": "usuario", "plan": "usuario",
             "clientes": "admin"}
AVAILABLE_PERMISSIONS = set(MODULES) | {f"{m}.{s}" for m, sections in MODULES.items() for s in sections}
PUESTO_NAME = re.compile(r"^[\w .-]{1,40}$")  # sin "/" : el nombre viaja en la URL


def _valid(modules):
    return [m for m in modules if m in AVAILABLE_PERMISSIONS]


@permissions_bp.route("/me", methods=["GET"])
@require_auth
def get_my_permissions():
    user = g.current_user
    granted = list(MODULES) if user["role"] == "admin" else effective_permissions(user)
    usable = [p for p in granted if ROLE_ONLY.get(p.split(".")[0], user["role"]) == user["role"]]
    return jsonify({"modules": usable})


@permissions_bp.route("", methods=["GET"])
@require_auth
@require_role("admin")
def get_all_permissions():
    # Lista y no dict: jsonify ordena las llaves y perderia el orden del catalogo.
    return jsonify({
        "modules": [{"id": m, "sections": sections} for m, sections in MODULES.items()],
        "permissions": read_json("permissions.json"),
        "puestos": load_puestos(),
    })


@permissions_bp.route("/<username>", methods=["PUT"])
@require_auth
@require_role("admin")
def update_permissions(username):
    if find_user(username=username) is None:
        return jsonify({"error": "El usuario no existe"}), 404

    modules = (request.get_json(silent=True) or {}).get("modules", [])
    if not isinstance(modules, list):
        return jsonify({"error": "modules debe ser una lista"}), 400

    valid_modules = _valid(modules)
    permissions = read_json("permissions.json")
    permissions[username] = valid_modules
    write_json("permissions.json", permissions)

    return jsonify({"username": username, "modules": valid_modules})


@permissions_bp.route("/puestos/<name>", methods=["PUT"])
@require_auth
@require_role("admin")
def update_puesto(name):
    """Crea el puesto o cambia sus permisos: todos los que lo tienen reciben el cambio."""
    if not PUESTO_NAME.match(name):
        return jsonify({"error": "El nombre del puesto va de 1 a 40 letras, números, espacios, . o -"}), 400

    modules = (request.get_json(silent=True) or {}).get("modules", [])
    if not isinstance(modules, list):
        return jsonify({"error": "modules debe ser una lista"}), 400

    puestos = load_puestos()
    puestos[name] = _valid(modules)
    write_json("puestos.json", puestos)

    return jsonify({"name": name, "modules": puestos[name]})


@permissions_bp.route("/puestos/<name>", methods=["DELETE"])
@require_auth
@require_role("admin")
def delete_puesto(name):
    puestos = load_puestos()
    if name not in puestos:
        return jsonify({"error": "El puesto no existe"}), 404
    if any(u.get("puesto") == name for u in load_users()):
        return jsonify({"error": "Hay usuarios con este puesto; cámbialos antes de borrarlo"}), 409

    del puestos[name]
    write_json("puestos.json", puestos)
    return jsonify({"name": name})
