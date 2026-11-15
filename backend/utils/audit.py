"""Bitacora (tabla auditoria_general, de solo insercion): lo que el admin opera en nombre de un cliente y los accesos denegados.

Ademas `tag` anota en cada operacion quien la hizo y por donde (lo que luego guarda `transacciones`).
"""
from flask import g, has_request_context, request

from db import connection as c
from db.connection import iso
from psycopg.types.json import Jsonb

TRADE_ACTIONS = ("buy", "sell")


def _ip():
    return (request.remote_addr or None) if has_request_context() else None


def _user_id(username):
    row = c.fetch_one("SELECT id FROM usuarios WHERE usuario = %s", (username,)) if username else None
    return row["id"] if row else None


def record_admin_trade(action, order):
    """Anota una compra/venta del admin; no hace nada si quien opera es el propio usuario."""
    if g.current_user["role"] != "admin":
        return
    client = request.args.get("client") or (request.get_json(silent=True) or {}).get("client")
    c.execute(
        "INSERT INTO auditoria_general (usuario_id, cliente_id, accion, objeto_tipo, despues, ip) VALUES (%s, %s, %s, %s, %s, %s)",
        (g.current_user["id"], _user_id(client), action, "transacciones",
         Jsonb({"symbol": order["symbol"], "quantity": order["quantity"], "asset_type": order["asset_type"],
                "client": client}), _ip()))


def record_denied(reason):
    """Los accesos denegados tambien quedan en la bitacora (resultado 'error')."""
    user = getattr(g, "current_user", None)
    c.execute("INSERT INTO auditoria_general (usuario_id, accion, objeto_tipo, resultado, motivo, ip) "
              "VALUES (%s, 'acceso_denegado', 'permisos', 'error', %s, %s)", (user["id"] if user else None, reason, _ip()))


def recent(limit=50):
    """Las ultimas operaciones del admin por clientes, de la mas nueva a la mas vieja (forma de audit.json)."""
    rows = c.fetch_all(
        "SELECT a.fecha_hora, a.accion, a.despues, adm.usuario AS admin, cl.usuario AS cliente FROM auditoria_general a "
        "LEFT JOIN usuarios adm ON adm.id = a.usuario_id LEFT JOIN usuarios cl ON cl.id = a.cliente_id "
        "WHERE a.accion = ANY(%s) ORDER BY a.fecha_hora DESC, a.id DESC LIMIT %s", (list(TRADE_ACTIONS), limit))
    return [{"date": iso(r["fecha_hora"]), "admin": r["admin"], "client": r["cliente"] or (r["despues"] or {}).get("client"),
             "action": r["accion"], "symbol": r["despues"]["symbol"], "quantity": r["despues"]["quantity"],
             "asset_type": r["despues"]["asset_type"]} for r in rows]


def tag(event):
    """Anota en una operacion quien la hizo (by, by_role) y por donde (origin): el cliente en la app, el admin en nombre
    del cliente, una orden programada o algo automatico (cupon, vencimiento). Respeta lo que la operacion ya traiga."""
    if "origin" in event:
        return event
    user = getattr(g, "current_user", None) if has_request_context() else None
    if event["side"] in ("coupon", "redeem") or user is None:
        event.update(by="sistema", by_role="sistema", origin="automático")
    else:
        event.update(by=user["username"], by_role=user["role"], origin="admin" if user["role"] == "admin" else "cliente")
    return event
