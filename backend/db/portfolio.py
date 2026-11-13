"""Carteras, ordenes de bonos y transacciones en PostgreSQL.

Los motores financieros (utils/stock_engine, bond_engine, bond_math) siguen siendo funciones puras sobre un dict de
cartera. `portfolio_tx(usuario)` abre UNA transaccion de base de datos, bloquea la fila del cliente (SELECT ... FOR UPDATE),
carga su cartera y sus ordenes en la forma de siempre, y al salir sin error escribe SOLO las diferencias:

    with portfolio_tx("ana") as s:
        s.portfolio["cash"] ...      # el motor modifica el dict
        s.events.append(evento)      # lo que el motor registro (compra, venta, cupon, vencimiento)

Todo o nada: si algo falla, se revierte la cartera, las ordenes y los movimientos juntos. Dos peticiones simultaneas sobre
el mismo cliente se serializan por el candado, asi una orden o un cupon no se ejecuta dos veces.
El efectivo NUNCA se escribe directo: cada evento inserta su movimiento en movimientos_efectivo y un trigger actualiza
usuarios.efectivo_mxn; al final se comprueba que el saldo de la base coincide con el del motor.
"""
import copy
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import psycopg

from db import connection as c
from db.connection import as_float, as_num, iso

SETTLEMENT_DAYS = 2  # igual que bond_math.SETTLEMENT_DAYS (la subasta es el martes y liquida el jueves)

REINVEST_TO_DB = {"none": "ninguna", "all": "todo", "same": "capital"}
REINVEST_FROM_DB = {v: k for k, v in REINVEST_TO_DB.items()}
ORDER_STATUS_TO_DB = {"pending": "pendiente", "executed": "ejecutada", "cancelled": "cancelada", "failed": "fallida"}
ORDER_STATUS_FROM_DB = {v: k for k, v in ORDER_STATUS_TO_DB.items()}
ORIGIN_TO_DB = {"cliente": "cliente", "admin": "admin", "automático": "automatico", "orden programada": "orden_programada"}
ORIGIN_FROM_DB = {v: k for k, v in ORIGIN_TO_DB.items()}


class CashMismatch(Exception):
    """El saldo que calculo el motor no coincide con la suma de movimientos: se revierte todo."""


def d(value, places=2):
    """float -> Decimal redondeado, para no depender de la conversion float8->numeric del servidor."""
    return None if value is None else Decimal(str(round(float(value), places)))


def day(value):
    return value if isinstance(value, date) and not isinstance(value, datetime) else date.fromisoformat(str(value)[:10])


# ------------------------------------------------------------------ lectura
def ensure_catalog(symbol, name, currency=None):
    """Da de alta el simbolo en acciones_catalogo la primera vez que se usa (el backend acepta cualquier simbolo de Yahoo)."""
    c.execute("INSERT INTO acciones_catalogo (simbolo, nombre, moneda) VALUES (%s, %s, COALESCE(%s::text, 'USD')) "
              "ON CONFLICT (simbolo) DO UPDATE SET moneda = COALESCE(%s::text, acciones_catalogo.moneda)",
              (symbol, (name or symbol)[:120], currency[:3] if currency else None, currency[:3] if currency else None))


def _stock_rows(user_id):
    return [{"symbol": r["simbolo"], "name": r["nombre"], "type": "accion", "currency": r["moneda"].strip(),
             "quantity": as_num(r["cantidad"]), "avg_cost": as_float(r["costo_promedio"]),
             "cost_basis_mxn": as_float(r["costo_base_mxn"]), "cost_estimated": r["costo_estimado"]}
            for r in c.fetch_all(
                "SELECT p.simbolo, a.nombre, a.moneda, p.cantidad, p.costo_promedio, p.costo_base_mxn, p.costo_estimado "
                "FROM posiciones_accion p JOIN acciones_catalogo a ON a.simbolo = p.simbolo WHERE p.usuario_id = %s ORDER BY p.id",
                (user_id,))]


def _lot_rows(user_id):
    lots = []
    for r in c.fetch_all(
            "SELECT l.uid, l.cantidad, l.fecha_compra, l.precio_compra, l.tasa_compra, l.reinversion_modo, l.proximo_cupon, "
            "l.cupones_pagados, e.instrumento_id, e.fecha_vencimiento, i.nombre, i.tipo, i.valor_nominal, i.dias_cupon "
            "FROM lotes_bono l JOIN emisiones e ON e.id = l.emision_id JOIN instrumentos i ON i.simbolo = e.instrumento_id "
            "WHERE l.usuario_id = %s AND l.estado = 'vigente' ORDER BY l.id", (user_id,)):
        lot = {"symbol": r["instrumento_id"], "name": r["nombre"], "type": "bono", "kind": r["tipo"],
               "quantity": as_num(r["cantidad"]), "nominal_value": as_num(r["valor_nominal"]),
               "rate_at_purchase": as_float(r["tasa_compra"]), "purchase_date": r["fecha_compra"].isoformat(),
               "maturity_date": r["fecha_vencimiento"].isoformat(), "lot_id": str(r["uid"]),
               "purchase_price": as_float(r["precio_compra"]), "reinvest": REINVEST_FROM_DB.get(r["reinversion_modo"], "none")}
        if r["tipo"] == "bono_m":
            lot.update(coupon_days=r["dias_cupon"], next_coupon_date=r["proximo_cupon"].isoformat(),
                       coupons_paid=r["cupones_pagados"])
        lots.append(lot)
    return lots


def get_user_row(username, lock=False):
    return c.fetch_one("SELECT id, rol, efectivo_mxn FROM usuarios WHERE usuario = %s" + (" FOR UPDATE" if lock else ""),
                       (username,))


def _load(user):
    if user is None or user["rol"] != "usuario":
        return {"cash": 0, "holdings": []}
    return {"cash": as_float(user["efectivo_mxn"]), "holdings": _stock_rows(user["id"]) + _lot_rows(user["id"])}


def get_portfolio(username):
    """Cartera de un usuario sin bloquear nada: {"cash", "holdings": [acciones y lotes vigentes]}."""
    return _load(get_user_row(username))


def balance_summary(username):
    """(efectivo, # de posiciones, # de ordenes pendientes): lo que impide dar de baja a un usuario."""
    user = get_user_row(username)
    if user is None:
        return 0, 0, 0
    pf = _load(user)
    pending = c.fetch_one("SELECT count(*) AS n FROM ordenes_bono WHERE usuario_id = %s AND estado = 'pendiente'", (user["id"],))["n"]
    return pf["cash"], len(pf["holdings"]), pending


def _order_rows(user_id):
    rows = c.fetch_all(
        "SELECT o.uid, o.origen, o.monto_mxn, o.reinversion_modo, o.estado, o.motivo_fallo, o.creada_en, s.instrumento_id, "
        "s.fecha_subasta, lo.uid AS lote_uid, eo.fecha_vencimiento AS lote_vence, i.nombre "
        "FROM ordenes_bono o JOIN subastas s ON s.id = o.subasta_id JOIN instrumentos i ON i.simbolo = s.instrumento_id "
        "LEFT JOIN lotes_bono lo ON lo.id = o.lote_origen_id LEFT JOIN emisiones eo ON eo.id = lo.emision_id "
        "WHERE o.usuario_id = %s ORDER BY o.id", (user_id,))
    return [{"source_lot_id": str(r["lote_uid"]) if r["lote_uid"] else None,
             "source_maturity": r["lote_vence"].isoformat() if r["lote_vence"] else None,
             "id": str(r["uid"]), "symbol": r["instrumento_id"], "name": r["nombre"], "quantity": None,
             "amount_mxn": as_float(r["monto_mxn"]), "reinvest": REINVEST_FROM_DB.get(r["reinversion_modo"], "none"),
             "source": "compra" if r["origen"] == "compra" else "reinversión",
             "scheduled_date": r["fecha_subasta"].isoformat(),
             "created_at": r["creada_en"].astimezone(timezone.utc).date().isoformat(),
             "status": ORDER_STATUS_FROM_DB[r["estado"]], "failure_reason": r["motivo_fallo"]} for r in rows]


def list_orders(username):
    user = get_user_row(username)
    if user is None:
        return []
    orders = _order_rows(user["id"])
    return sorted(orders, key=lambda o: o["created_at"], reverse=True)  # estable: empates en orden de creacion


def catalog_bonds():
    """Catalogo de bonos con la misma forma de assets.json."""
    bonds = []
    for r in c.fetch_all("SELECT i.simbolo, i.nombre, i.tipo, i.valor_nominal, i.plazo_dias, i.dias_cupon, s.codigo "
                         "FROM instrumentos i LEFT JOIN series_mercado s ON s.id = i.serie_subasta_id "
                         "WHERE i.activo ORDER BY i.simbolo"):
        bond = {"symbol": r["simbolo"], "name": r["nombre"], "type": "bono", "kind": r["tipo"], "source": "banxico",
                "series_id": r["codigo"], "nominal_value": as_num(r["valor_nominal"]), "term_days": r["plazo_dias"]}
        if r["dias_cupon"]:
            bond["coupon_days"] = r["dias_cupon"]
        bonds.append(bond)
    order = {"CETES28": 0, "CETES91": 1, "CETES182": 2, "CETES364": 3}
    return sorted(bonds, key=lambda b: (order.get(b["symbol"], 9), b["symbol"]))


# ------------------------------------------------------------------ transacciones (forma de transactions.json)
def _tx_dict(r):
    if r["tipo_activo"] == "accion":
        t = {"id": str(r["uid"]), "date": iso(r["fecha_hora"]), "type": "accion", "side": "buy" if r["lado"] == "compra" else "sell",
             "symbol": r["simbolo"], "name": r["nombre"], "quantity": as_num(r["cantidad"]), "price": as_float(r["precio"]),
             "currency": r["moneda"].strip(), "fx_rate": as_float(r["tipo_cambio"]), "total_mxn": as_float(r["total_mxn"])}
    else:
        t = {"id": str(r["uid"]), "date": iso(r["fecha_hora"]), "type": "bono", "side": "buy" if r["lado"] == "compra" else "sell",
             "symbol": r["simbolo"], "name": r["nombre"], "quantity": as_num(r["cantidad"]), "rate": as_float(r["tasa"]),
             "total_mxn": as_float(r["total_mxn"])}
    if r["utilidad_realizada_mxn"] is not None:
        t["realized_pnl_mxn"] = as_float(r["utilidad_realizada_mxn"])
    t.update(by=r["por"] or "sistema", by_role=r["rol_de_quien_la_hizo"], origin=ORIGIN_FROM_DB[r["origen"]])
    return t


def _movement_dict(r):
    t = {"id": str(r["uid"]), "date": iso(r["fecha_hora"]), "type": "bono", "side": "coupon" if r["tipo"] == "cupon" else "redeem",
         "symbol": r["simbolo"], "name": r["nombre"], "quantity": as_num(r["cantidad"]), "rate": as_float(r["tasa"]),
         "total_mxn": as_float(r["monto_mxn"])}
    if r["utilidad_realizada_mxn"] is not None:
        t["realized_pnl_mxn"] = as_float(r["utilidad_realizada_mxn"])
    t.update(by="sistema", by_role="sistema", origin="automático")
    return t


TX_SQL = ("SELECT t.uid, t.fecha_hora, t.tipo_activo, t.lado, t.cantidad, t.precio, t.moneda, t.tipo_cambio, t.tasa, t.total_mxn, "
          "t.utilidad_realizada_mxn, t.rol_de_quien_la_hizo, t.origen, t.id, cl.usuario AS cliente, h.usuario AS por, "
          "COALESCE(t.simbolo_accion, e.instrumento_id) AS simbolo, COALESCE(a.nombre, i.nombre) AS nombre "
          "FROM transacciones t JOIN usuarios cl ON cl.id = t.usuario_id LEFT JOIN usuarios h ON h.id = t.hecha_por "
          "LEFT JOIN acciones_catalogo a ON a.simbolo = t.simbolo_accion LEFT JOIN lotes_bono l ON l.id = t.lote_id "
          "LEFT JOIN emisiones e ON e.id = l.emision_id LEFT JOIN instrumentos i ON i.simbolo = e.instrumento_id")
MOV_SQL = ("SELECT m.uid, m.fecha_hora, m.tipo, m.cantidad, m.tasa, m.monto_mxn, m.utilidad_realizada_mxn, m.id, cl.usuario AS cliente, "
           "e.instrumento_id AS simbolo, i.nombre FROM movimientos_efectivo m JOIN usuarios cl ON cl.id = m.usuario_id "
           "JOIN lotes_bono l ON l.id = m.lote_id JOIN emisiones e ON e.id = l.emision_id "
           "JOIN instrumentos i ON i.simbolo = e.instrumento_id WHERE m.tipo IN ('cupon', 'vencimiento')")


def transactions_by_user(username=None):
    """{usuario: [movimiento, ...]} del mas viejo al mas nuevo, con las compras/ventas y los cupones/vencimientos.
    Con `username` solo ese cliente (la llave siempre existe)."""
    cond, args = (" WHERE cl.usuario = %s", (username,)) if username else ("", ())
    mcond = " AND cl.usuario = %s" if username else ""
    rows = [(r["fecha_hora"], 0, r["id"], r["cliente"], _tx_dict(r)) for r in c.fetch_all(TX_SQL + cond, args)]
    rows += [(r["fecha_hora"], 1, r["id"], r["cliente"], _movement_dict(r)) for r in c.fetch_all(MOV_SQL + mcond, args)]
    result = {username: []} if username else {}
    for _, _, _, owner, item in sorted(rows, key=lambda x: x[:3]):
        result.setdefault(owner, []).append(item)
    return result


def transactions_for(username):
    return transactions_by_user(username)[username]


# ------------------------------------------------------------------ escritura atomica
class PortfolioSession:
    def __init__(self, username, user):
        self.username, self.user = username, user
        self.portfolio = _load(user)
        self.orders = _order_rows(user["id"]) if user and user["rol"] == "usuario" else []
        self.events = []
        self._before = copy.deepcopy(self.portfolio)
        self._orders_before = {o["id"]: dict(o) for o in self.orders}

    # --------------------------------------------------------- helpers
    def _user_id(self, username):
        if not username or username == "sistema":
            return None
        row = c.fetch_one("SELECT id FROM usuarios WHERE usuario = %s", (username,))
        return row["id"] if row else None

    def _emission(self, lot):
        kind_m = lot["kind"] == "bono_m"
        clave = f"{lot['symbol']}-{lot['purchase_date'].replace('-', '')}"
        return c.fetch_one(
            "INSERT INTO emisiones (instrumento_id, clave, fecha_emision, fecha_vencimiento, tasa_cupon) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT ON CONSTRAINT uq_emision_clave DO UPDATE SET clave = EXCLUDED.clave RETURNING id",
            (lot["symbol"], clave, day(lot["purchase_date"]), day(lot["maturity_date"]),
             d(lot["rate_at_purchase"], 6) if kind_m else None))["id"]

    def _auction(self, symbol, scheduled):
        auction = day(scheduled)
        plazo = c.fetch_one("SELECT plazo_dias FROM instrumentos WHERE simbolo = %s", (symbol,))["plazo_dias"]
        return c.fetch_one(
            "INSERT INTO subastas (instrumento_id, fecha_subasta, fecha_colocacion, plazo_dias_reales) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (instrumento_id, fecha_colocacion) DO UPDATE SET instrumento_id = EXCLUDED.instrumento_id RETURNING id",
            (symbol, auction, auction + timedelta(days=SETTLEMENT_DAYS), plazo))["id"]

    # --------------------------------------------------------- guardado
    def flush(self):
        uid, before, after = self.user["id"], self._before, self.portfolio
        events = [self._complete(e) for e in self.events]

        # 1) posiciones de acciones
        old = {h["symbol"]: h for h in before["holdings"] if h["type"] == "accion"}
        new = {h["symbol"]: h for h in after["holdings"] if h["type"] == "accion"}
        for symbol, h in new.items():
            if h != old.get(symbol):
                ensure_catalog(symbol, h["name"], h.get("currency"))
                c.execute(
                    "INSERT INTO posiciones_accion (usuario_id, simbolo, cantidad, costo_promedio, costo_base_mxn, costo_estimado) "
                    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (usuario_id, simbolo) DO UPDATE SET cantidad = EXCLUDED.cantidad, "
                    "costo_promedio = EXCLUDED.costo_promedio, costo_base_mxn = EXCLUDED.costo_base_mxn, costo_estimado = EXCLUDED.costo_estimado",
                    (uid, symbol, d(h["quantity"], 6), d(h["avg_cost"], 6), d(h["cost_basis_mxn"]), bool(h.get("cost_estimated"))))
        for symbol in old.keys() - new.keys():
            c.execute("DELETE FROM posiciones_accion WHERE usuario_id = %s AND simbolo = %s", (uid, symbol))

        # 2) lotes de bonos: nuevos, cambios y los que salieron (vencido o vendido)
        lot_old = {h["lot_id"]: h for h in before["holdings"] if h["type"] == "bono"}
        lot_new = {h["lot_id"]: h for h in after["holdings"] if h["type"] == "bono"}
        redeemed = {e["lot_id"] for e in events if e["side"] == "redeem"}
        for lot_id, lot in lot_new.items():
            if lot_id not in lot_old:
                c.execute(
                    "INSERT INTO lotes_bono (uid, usuario_id, emision_id, cantidad, fecha_compra, precio_compra, tasa_compra, "
                    "reinversion_modo, proximo_cupon, cupones_pagados) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (lot_id, uid, self._emission(lot), d(lot["quantity"], 6), day(lot["purchase_date"]), d(lot["purchase_price"], 7),
                     d(lot["rate_at_purchase"], 6), REINVEST_TO_DB[lot.get("reinvest", "none")],
                     day(lot["next_coupon_date"]) if lot.get("next_coupon_date") else None, lot.get("coupons_paid", 0)))
            elif lot != lot_old[lot_id]:
                c.execute("UPDATE lotes_bono SET cantidad = %s, reinversion_modo = %s, proximo_cupon = %s, cupones_pagados = %s "
                          "WHERE uid = %s AND usuario_id = %s",
                          (d(lot["quantity"], 6), REINVEST_TO_DB[lot.get("reinvest", "none")],
                           day(lot["next_coupon_date"]) if lot.get("next_coupon_date") else None, lot.get("coupons_paid", 0),
                           lot_id, uid))
        for lot_id in lot_old.keys() - lot_new.keys():
            if lot_id in redeemed:
                c.execute("UPDATE lotes_bono SET estado = 'vencido' WHERE uid = %s", (lot_id,))
            else:
                c.execute("UPDATE lotes_bono SET estado = 'vendido', cantidad = 0 WHERE uid = %s", (lot_id,))
        lot_ids = {str(r["uid"]): r["id"] for r in c.fetch_all("SELECT uid, id FROM lotes_bono WHERE usuario_id = %s", (uid,))}

        # 3) cupones y vencimientos (entradas de efectivo) -> movimientos; de aqui salen los ids que usan las reinversiones
        movement_ids = {}
        for e in events:
            if e["side"] in ("coupon", "redeem"):
                row = c.fetch_one(
                    "INSERT INTO movimientos_efectivo (uid, usuario_id, fecha_hora, tipo, monto_mxn, lote_id, cantidad, tasa, "
                    "utilidad_realizada_mxn) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (e["id"], uid, e["date"], "cupon" if e["side"] == "coupon" else "vencimiento", d(e["total_mxn"]),
                     lot_ids[e["lot_id"]], d(e["quantity"], 6), d(e.get("rate"), 6), d(e.get("realized_pnl_mxn"))))
                movement_ids[e["id"]] = row["id"]

        # 4) ordenes nuevas o modificadas
        order_ids = {str(r["uid"]): r["id"] for r in c.fetch_all("SELECT uid, id FROM ordenes_bono WHERE usuario_id = %s", (uid,))}
        for o in self.orders:
            prev = self._orders_before.get(o["id"])
            if prev is None:
                lote = lot_ids.get(o["source_lot_id"]) if o.get("source_lot_id") else None
                mov = movement_ids.get(o.get("coupon_event_id")) if o.get("coupon_event_id") else None
                origin = "compra" if o["source"] == "compra" else ("reinversion_vencimiento" if lote else "reinversion_cupon")
                if origin == "reinversion_vencimiento" and not lote or origin == "reinversion_cupon" and not mov:
                    raise ValueError(f"La orden {o['id']} de reinversion no tiene su lote o cupon de origen")
                row = c.fetch_one(
                    "INSERT INTO ordenes_bono (uid, usuario_id, subasta_id, origen, monto_mxn, reinversion_modo, lote_origen_id, "
                    "movimiento_origen_id, estado, motivo_fallo, creada_en, ejecutada_en, cancelada_en) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), CASE WHEN %s = 'ejecutada' THEN now() END, "
                    "CASE WHEN %s = 'cancelada' THEN now() END) RETURNING id",
                    (o["id"], uid, self._auction(o["symbol"], o["scheduled_date"]), origin, d(o["amount_mxn"]),
                     REINVEST_TO_DB[o.get("reinvest", "none")], lote, mov, ORDER_STATUS_TO_DB[o["status"]], o.get("failure_reason"),
                     ORDER_STATUS_TO_DB[o["status"]], ORDER_STATUS_TO_DB[o["status"]]))
                order_ids[o["id"]] = row["id"]
            elif {k: o.get(k) for k in prev} != prev:
                c.execute(
                    "UPDATE ordenes_bono SET estado = %s, motivo_fallo = %s, monto_mxn = %s, reinversion_modo = %s, subasta_id = %s, "
                    "ejecutada_en = CASE WHEN %s = 'ejecutada' THEN COALESCE(ejecutada_en, now()) ELSE ejecutada_en END, "
                    "cancelada_en = CASE WHEN %s = 'cancelada' THEN COALESCE(cancelada_en, now()) ELSE cancelada_en END "
                    "WHERE uid = %s AND usuario_id = %s",
                    (ORDER_STATUS_TO_DB[o["status"]], o.get("failure_reason"), d(o["amount_mxn"]),
                     REINVEST_TO_DB[o.get("reinvest", "none")], self._auction(o["symbol"], o["scheduled_date"]),
                     ORDER_STATUS_TO_DB[o["status"]], ORDER_STATUS_TO_DB[o["status"]], o["id"], uid))
            lot_uid = o.get("executed_lot_id")
            if lot_uid and o["status"] == "executed" and not (prev and prev["status"] == "executed"):
                c.execute("UPDATE lotes_bono SET orden_id = %s WHERE uid = %s", (order_ids[o["id"]], lot_uid))
                c.execute("UPDATE subastas SET realizada = TRUE, emision_id = (SELECT emision_id FROM lotes_bono WHERE uid = %s) "
                          "WHERE id = (SELECT subasta_id FROM ordenes_bono WHERE uid = %s) AND NOT realizada", (lot_uid, o["id"]))

        # 5) compras y ventas -> transacciones + movimiento (primero las que meten dinero, para que el saldo nunca baje de 0)
        trades = [e for e in events if e["side"] in ("buy", "sell")]
        for e in sorted(trades, key=lambda e: e["side"] != "sell"):
            self._insert_trade(e, uid, lot_ids, order_ids)

        # 6) el saldo de la base debe ser el que calculo el motor
        saldo = as_float(c.fetch_one("SELECT efectivo_mxn FROM usuarios WHERE id = %s", (uid,))["efectivo_mxn"])
        if abs(saldo - after["cash"]) > 0.005:
            raise CashMismatch(f"Saldo en base {saldo} distinto al del motor {after['cash']}")

    def _complete(self, event):
        from utils import audit
        return audit.tag(event)

    def _insert_trade(self, e, uid, lot_ids, order_ids):
        accion = e["type"] == "accion"
        total = float(e["total_mxn"])
        if total <= 0:
            raise ValueError("El importe de la operacion debe ser mayor que 0")
        if accion:
            ensure_catalog(e["symbol"], e.get("name"), e.get("currency"))
            price, currency, fx = e["price"], e["currency"], e["fx_rate"]
            lot = None
        else:
            lot = lot_ids[e["lot_id"]]
            price = round(total / float(e["quantity"]), 7)
            currency, fx = "MXN", 1
        row = c.fetch_one(
            "INSERT INTO transacciones (uid, usuario_id, fecha_hora, tipo_activo, lado, simbolo_accion, lote_id, cantidad, precio, "
            "moneda, tipo_cambio, tasa, total_mxn, utilidad_realizada_mxn, hecha_por, rol_de_quien_la_hizo, origen, orden_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (e["id"], uid, e["date"], e["type"], "compra" if e["side"] == "buy" else "venta", e["symbol"] if accion else None, lot,
             d(e["quantity"], 6), d(price, 7), currency, d(fx, 8), None if accion else d(e.get("rate"), 6), d(total),
             d(e.get("realized_pnl_mxn")), self._user_id(e.get("by")), e["by_role"], ORIGIN_TO_DB[e["origin"]],
             order_ids.get(e.get("order_id")) if e.get("order_id") else None))
        c.execute("INSERT INTO movimientos_efectivo (usuario_id, fecha_hora, tipo, monto_mxn, transaccion_id, hecho_por) "
                  "VALUES (%s, %s, %s, %s, %s, %s)",
                  (uid, e["date"], "compra" if e["side"] == "buy" else "venta", d(-total if e["side"] == "buy" else total),
                   row["id"], self._user_id(e.get("by"))))


@contextmanager
def portfolio_tx(username):
    """Transaccion de cartera de `username` (ver el docstring del modulo). Rechaza usuarios que no existen."""
    with c.transaction():
        user = get_user_row(username, lock=True)
        if user is None:
            raise LookupError(f"Usuario inexistente: {username}")
        session = PortfolioSession(username, user)
        yield session
        if user["rol"] == "usuario":
            session.flush()
        elif session.events or session.portfolio != session._before:
            raise ValueError("Solo los clientes tienen cartera")
