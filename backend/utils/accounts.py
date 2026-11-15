"""Usuarios, puestos y clientes asignados (PostgreSQL: usuarios, puestos y asignaciones_consultor).

Roles: "usuario" compra, vende y ve su cartera; "consultor" analiza las inversiones de los
usuarios que tiene asignados; "admin" ve todo y reparte los modulos. Un puesto es un lote de
permisos con nombre: quien lo tiene recibe esos modulos ademas de los suyos.
Las funciones devuelven dicts con la misma forma que tenia users.json (username, name, role, puesto, consultant...).
"""
from db import accounts as repo

ROLES = ("usuario", "consultor", "admin")


def load_users():
    return repo.list_users()


def find_user(**match):
    """Primer usuario cuyos campos coinciden: find_user(username="ana") o find_user(id=2)."""
    if set(match) == {"username"}:
        return repo.get_user(username=match["username"])
    if set(match) == {"id"}:
        return repo.get_user(id=match["id"])
    return next((u for u in load_users() if all(u.get(k) == v for k, v in match.items())), None)


def load_puestos():
    return repo.load_puestos()


def effective_permissions(user):
    """Permisos propios del usuario mas los de su puesto. `user` trae username y puesto."""
    return repo.own_permissions(user["username"]) + load_puestos().get(user.get("puesto"), [])


def clients_of(consultant):
    """Usuarios asignados a un consultor (de momento solo usuarios, no otros consultores)."""
    return repo.clients_of(consultant)
