"""Usuarios, puestos y clientes asignados (lee users.json y puestos.json).

Roles: "usuario" compra, vende y ve su cartera; "consultor" analiza las inversiones de los
usuarios que tiene asignados; "admin" ve todo y reparte los modulos. Un puesto es un lote de
permisos con nombre: quien lo tiene recibe esos modulos ademas de los suyos.
"""
from utils.data_store import read_json

ROLES = ("usuario", "consultor", "admin")

# Puestos de arranque mientras no exista puestos.json (p. ej. un volumen con datos anteriores).
DEFAULT_PUESTOS = {
    "Inversionista": ["portfolio", "trading", "risk", "avisos"],
    "Consultor": ["consultor"],
}


def load_users():
    return read_json("users.json")["users"]


def find_user(**match):
    """Primer usuario cuyos campos coinciden: find_user(username="ana") o find_user(id=2)."""
    return next((u for u in load_users() if all(u.get(k) == v for k, v in match.items())), None)


def load_puestos():
    try:
        return read_json("puestos.json")
    except FileNotFoundError:
        return dict(DEFAULT_PUESTOS)


def effective_permissions(user):
    """Permisos propios del usuario mas los de su puesto. `user` trae username y puesto."""
    own = read_json("permissions.json").get(user["username"], [])
    return own + load_puestos().get(user.get("puesto"), [])


def clients_of(consultant):
    """Usuarios asignados a un consultor (de momento solo usuarios, no otros consultores)."""
    return [u for u in load_users() if u["role"] == "usuario" and u.get("consultant") == consultant]
