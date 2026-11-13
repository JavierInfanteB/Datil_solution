"""Importa los JSON de data/ a PostgreSQL (migracion unica, repetible sin duplicar).

Uso:  python import_json.py --data-dir ../../data [--dry-run] [--report ruta.json]
(o desde run_migrations.py --import-json ../../data). Se conecta como el propietario de la base (variables DB_* /
POSTGRES_*), igual que run_migrations.py.

Reglas:
  * Se conservan ids de usuarios, hashes de contrasena (nunca texto plano), uuid de transacciones, ordenes, lotes, avisos,
    metas, notas y alertas, cantidades, importes y fechas.
  * Idempotente: cada fila se identifica por su id/uuid original y se inserta solo si falta (ON CONFLICT DO NOTHING).
    Volver a correrlo no duplica nada ni toca el efectivo de un cliente que ya tiene movimientos.
  * Todo corre en UNA transaccion: si algo truena, la base queda como estaba.
  * Los datos que no caben en el modelo o no cuadran NO se inventan: se reportan en "warnings" (y se omiten).
  * Los JSON no se modifican ni se borran: siguen siendo el respaldo.
"""
import argparse
import json
import os
import sys
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from werkzeug.security import generate_password_hash

NS = uuid.UUID("5b0d1c52-2d9c-4a9e-8f51-0a1d71e0d4a7")  # namespace fijo: los uuid derivados son estables entre corridas
ROLES = ("admin", "consultor", "usuario")
ORIGIN = {"cliente": "cliente", "admin": "admin", "automático": "automatico", "automatico": "automatico",
          "orden programada": "orden_programada"}
REINV = {"none": "ninguna", "all": "todo", "same": "capital"}
ORDER_STATUS = {"pending": "pendiente", "executed": "ejecutada", "cancelled": "cancelada", "failed": "fallida"}
SETTLEMENT_DAYS = 2


def D(value, places=2):
    return None if value is None else Decimal(str(round(float(value), places)))


def to_dt(value):
    if value is None:
        return None
    text = str(value)
    dt = datetime.fromisoformat(text) if "T" in text or " " in text else datetime.fromisoformat(text + "T00:00:00+00:00")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def to_date(value):
    return date.fromisoformat(str(value)[:10])


def uid_of(value, key):
    """El uuid original si lo es; si no, uno derivado y estable."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return uuid.uuid5(NS, f"{key}:{value}")


class Importer:
    def __init__(self, conn, data_dir):
        self.conn, self.dir = conn, Path(data_dir)
        self.count, self.warnings = Counter(), []

    # ------------------------------------------------------------ utilidades
    def warn(self, msg):
        self.warnings.append(msg)

    def load(self, name, default):
        path = self.dir / name
        if not path.exists():
            return default
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def ex(self, sql, params=()):
        return self.conn.execute(sql, params)

    def insert(self, entity, sql, params):
        """Ejecuta un INSERT ... ON CONFLICT DO NOTHING RETURNING id; cuenta nuevos y ya existentes."""
        row = self.conn.execute(sql, params).fetchone()
        self.count[f"{entity}: importados" if row else f"{entity}: ya existian"] += 1
        return row["id"] if row else None

    def uid_user(self, username):
        row = self.one("SELECT id, rol FROM usuarios WHERE usuario = %s", (username,))
        return row

    # ------------------------------------------------------------ pasos
    def puestos(self):
        data = self.load("puestos.json", None)
        if data is None:
            return
        for name, perms in data.items():
            self.insert("puestos", "INSERT INTO puestos (nombre, permisos) VALUES (%s, %s) ON CONFLICT (nombre) DO NOTHING RETURNING id",
                        (name, list(perms)))

    def users(self):
        users = self.load("users.json", {"users": []})["users"]
        perms = self.load("permissions.json", {})
        names = {u["username"] for u in users}
        for owner in perms:
            if owner not in names:
                self.warn(f"permissions.json: el usuario '{owner}' no existe en users.json (permisos omitidos)")
        for u in users:
            name, role = u["username"], u.get("role")
            if role not in ROLES:
                self.warn(f"users.json: '{name}' tiene un rol invalido ({role!r}); se omite")
                continue
            pw = u.get("password_hash")
            if not pw:
                self.warn(f"users.json: '{name}' no tiene password_hash; se genero la contrasena inicial (igual al usuario; en 'admin', 'admin'). Cambiala.")
                pw = generate_password_hash("admin" if name == "admin" else name)
            elif not pw.startswith(("scrypt:", "pbkdf2:")):
                self.warn(f"users.json: el hash de '{name}' no tiene formato de Werkzeug; se conserva tal cual")
            estado = "baja" if u.get("deleted") else "suspendido" if u.get("disabled") else "activo"
            puesto = u.get("puesto")
            if puesto and not self.one("SELECT 1 AS x FROM puestos WHERE nombre = %s", (puesto,)):
                self.warn(f"users.json: el puesto '{puesto}' de '{name}' no existe; queda sin puesto")
                puesto = None
            own = [p for p in perms.get(name, [])]
            self.insert("usuarios",
                        "INSERT INTO usuarios (id, usuario, nombre, contrasena_hash, rol, puesto_id, permisos, estado, baja_en) "
                        "VALUES (%s, %s, %s, %s, %s, (SELECT id FROM puestos WHERE nombre = %s), %s, %s, "
                        "CASE WHEN %s = 'baja' THEN now() END) ON CONFLICT (usuario) DO NOTHING RETURNING id",
                        (u.get("id"), name, u["name"], pw, role, puesto, own, estado, estado))
        self.ex("SELECT setval(pg_get_serial_sequence('usuarios', 'id'), GREATEST((SELECT max(id) FROM usuarios), 1))")
        for u in users:  # asignaciones de consultor
            boss = u.get("consultant")
            if not boss:
                continue
            client, consultant = self.uid_user(u["username"]), self.uid_user(boss)
            if not client or client["rol"] != "usuario" or not consultant or consultant["rol"] != "consultor":
                self.warn(f"users.json: la asignacion de '{u['username']}' al consultor '{boss}' no es valida (cliente 'usuario' + consultor 'consultor'); se omite")
                continue
            if self.one("SELECT 1 AS x FROM asignaciones_consultor WHERE cliente_id = %s AND hasta IS NULL", (client["id"],)):
                self.count["asignaciones: ya existian"] += 1
                continue
            self.ex("INSERT INTO asignaciones_consultor (cliente_id, consultor_id, desde) VALUES (%s, %s, CURRENT_DATE)",
                    (client["id"], consultant["id"]))
            self.count["asignaciones: importados"] += 1

    def catalog(self):
        for a in self.load("assets.json", []):
            if a.get("type") != "bono":
                continue
            if self.one("SELECT 1 AS x FROM instrumentos WHERE simbolo = %s", (a["symbol"],)):
                continue
            bono_m = a.get("kind") == "bono_m"
            serie = self.insert("series_mercado", "INSERT INTO series_mercado (fuente, codigo, nombre, frecuencia) VALUES ('banxico', %s, %s, 'semanal') "
                                "ON CONFLICT (fuente, codigo) DO NOTHING RETURNING id", (a["series_id"], a["name"]))
            serie = serie or self.one("SELECT id FROM series_mercado WHERE fuente = 'banxico' AND codigo = %s", (a["series_id"],))["id"]
            self.insert("instrumentos",
                        "INSERT INTO instrumentos (simbolo, nombre, tipo, tipo_tasa, valor_nominal, plazo_dias, dias_cupon, serie_subasta_id) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (simbolo) DO NOTHING RETURNING simbolo AS id",
                        (a["symbol"], a["name"], "bono_m" if bono_m else "cetes", "fija" if bono_m else "cero", a["nominal_value"],
                         a["term_days"], a.get("coupon_days") if bono_m else None, serie))

    def instrument(self, symbol):
        return self.one("SELECT * FROM instrumentos WHERE simbolo = %s", (symbol,))

    def emission(self, symbol, purchase, maturity, rate, kind):
        return self.one(
            "INSERT INTO emisiones (instrumento_id, clave, fecha_emision, fecha_vencimiento, tasa_cupon) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT ON CONSTRAINT uq_emision_clave DO UPDATE SET clave = EXCLUDED.clave RETURNING id",
            (symbol, f"{symbol}-{purchase:%Y%m%d}", purchase, maturity, D(rate, 6) if kind == "bono_m" else None))["id"]

    def auction(self, symbol, scheduled, inst):
        scheduled = to_date(scheduled)
        return self.one(
            "INSERT INTO subastas (instrumento_id, fecha_subasta, fecha_colocacion, plazo_dias_reales) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (instrumento_id, fecha_colocacion) DO UPDATE SET instrumento_id = EXCLUDED.instrumento_id RETURNING id",
            (symbol, scheduled, scheduled + timedelta(days=SETTLEMENT_DAYS), inst["plazo_dias"]))["id"]

    def ensure_stock(self, symbol, name, currency):
        self.ex("INSERT INTO acciones_catalogo (simbolo, nombre, moneda) VALUES (%s, %s, %s) ON CONFLICT (simbolo) DO NOTHING",
                (symbol, (name or symbol)[:120], (currency or "USD")[:3]))

    def portfolios(self):
        portfolios = self.load("portfolios.json", {})
        transactions = self.load("transactions.json", {})
        orders = self.load("orders.json", {})
        users = {u["usuario"]: u for u in self.conn.execute("SELECT id, usuario, rol FROM usuarios").fetchall()}
        for name in sorted(set(portfolios) | set(transactions) | set(orders)):
            user = users.get(name)
            if user is None:
                self.warn(f"portfolios/transactions/orders: '{name}' no es un usuario; se omite")
                continue
            if user["rol"] != "usuario":
                pf = portfolios.get(name, {})
                self.warn(f"'{name}' es {user['rol']} y no puede tener cartera (el modelo exige rol 'usuario'): se omite su cartera "
                          f"(efectivo ${pf.get('cash', 0)}, {len(pf.get('holdings', []))} posiciones, {len(transactions.get(name, []))} transacciones, "
                          f"{len(orders.get(name, []))} ordenes). Sigue en el JSON de respaldo")
                continue
            with self.conn.transaction():  # un cliente con datos malos no tumba a los demas
                self.one_portfolio(user, portfolios.get(name, {"cash": 0, "holdings": []}), transactions.get(name, []), orders.get(name, []))

    def one_portfolio(self, user, pf, txs, orders):
        uid, name = user["id"], user["usuario"]
        fresh = self.one("SELECT count(*) AS n FROM movimientos_efectivo WHERE usuario_id = %s", (uid,))["n"] == 0
        lots = {}  # lot_id -> (id de BD, dict original)

        for h in pf.get("holdings", []):
            if h["type"] == "accion":
                self.ensure_stock(h["symbol"], h.get("name"), h.get("currency", "USD"))
                self.insert("posiciones_accion",
                            "INSERT INTO posiciones_accion (usuario_id, simbolo, cantidad, costo_promedio, costo_base_mxn, costo_estimado) "
                            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (usuario_id, simbolo) DO NOTHING RETURNING id",
                            (uid, h["symbol"], D(h["quantity"], 6), D(h.get("avg_cost") or 0, 6), D(h.get("cost_basis_mxn") or 0),
                             bool(h.get("cost_estimated", h.get("avg_cost") is None))))
            else:
                self.import_lot(uid, name, h, lots)

        events = self.build_events(uid, name, txs, lots)
        # efectivo: deposito inicial para que "saldo = suma de movimientos" y todos los saldos intermedios sean >= 0
        adjust = None
        if fresh and (pf.get("cash", 0) or events):
            adjust = self.opening_balance(uid, name, float(pf.get("cash", 0)), events)
        for ev in events:
            self.import_event(uid, name, ev, lots)
        if adjust:  # va DESPUES de los eventos: antes dejaria el saldo en negativo a media historia
            self.ex("INSERT INTO movimientos_efectivo (uid, usuario_id, fecha_hora, tipo, monto_mxn, nota) VALUES (%s, %s, %s, 'retiro', %s, %s) "
                    "ON CONFLICT (uid) DO NOTHING", (uuid.uuid5(NS, f"ajuste-migracion:{name}"), uid, adjust[1], D(adjust[0]),
                                                      "Ajuste de conciliacion de la migracion"))
            self.count["movimientos_efectivo: ajustes de conciliacion"] += 1
        self.import_orders(uid, name, orders, lots)

    def import_lot(self, uid, name, h, lots, uid_value=None):
        inst = self.instrument(h["symbol"])
        if inst is None or "maturity_date" not in h or "purchase_date" not in h:
            self.warn(f"{name}: el lote de {h['symbol']} no se puede importar (instrumento desconocido o sin fechas)")
            return None
        purchase, maturity = to_date(h["purchase_date"]), to_date(h["maturity_date"])
        kind = inst["tipo"]
        price = h.get("purchase_price", h.get("nominal_value"))
        lot_uid = uid_value or uid_of(h.get("lot_id"), f"lote:{name}:{h['symbol']}:{h['purchase_date']}")
        emis = self.emission(h["symbol"], purchase, maturity, h["rate_at_purchase"], kind)
        lid = self.insert(
            "lotes_bono",
            "INSERT INTO lotes_bono (uid, usuario_id, emision_id, cantidad, fecha_compra, precio_compra, tasa_compra, reinversion_modo, "
            "proximo_cupon, cupones_pagados, estado) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (uid) DO NOTHING RETURNING id",
            (lot_uid, uid, emis, D(h["quantity"], 6), purchase, D(price, 7), D(h["rate_at_purchase"], 6),
             REINV.get(h.get("reinvest", "none"), "ninguna"),
             to_date(h["next_coupon_date"]) if h.get("next_coupon_date") else None, h.get("coupons_paid", 0),
             h.get("_estado", "vigente")))
        lid = lid or self.one("SELECT id FROM lotes_bono WHERE uid = %s", (lot_uid,))["id"]
        lots[str(lot_uid)] = (lid, h)
        if h.get("lot_id"):
            lots[str(h["lot_id"])] = (lid, h)
        return lid

    def build_events(self, uid, name, txs, lots):
        """Transacciones del JSON -> eventos listos para insertar, ya enlazados a su lote. Los que no se pueden enlazar se omiten."""
        events = []
        synthetic = {}  # (simbolo, tasa, cantidad) -> lote historico
        for t in txs:
            ev = {"t": t, "when": to_dt(t["date"]), "lot": None}
            if t["type"] == "bono":
                lot = self.match_lot(t, lots, synthetic)
                if lot is None and t["side"] == "redeem":
                    lot = self.historical_lot(uid, name, t, lots, synthetic)
                if lot is None:
                    self.warn(f"{name}: la transaccion {t['id']} ({t['side']} {t['symbol']}) no se puede enlazar a un lote y se omite")
                    continue
                ev["lot"] = lot
            if float(t["total_mxn"]) <= 0 or float(t["quantity"]) <= 0:
                self.warn(f"{name}: la transaccion {t['id']} tiene importe o cantidad <= 0 y se omite")
                continue
            events.append(ev)
        return sorted(events, key=lambda e: (e["when"], e["t"]["side"] not in ("sell", "coupon", "redeem")))

    def match_lot(self, t, lots, synthetic):
        for lid, h in {v[0]: v for v in lots.values()}.items():
            lot = h[1]
            if lot["symbol"] == t["symbol"] and abs(float(lot["rate_at_purchase"]) - float(t.get("rate", -1))) < 1e-9 \
                    and abs(float(lot["quantity"]) - float(t["quantity"])) < 1e-9:
                if t["side"] == "redeem" and lot["maturity_date"][:10] != t["date"][:10]:
                    continue  # un vencimiento solo pertenece al lote que vence ese dia, no a otro igual que sigue vigente
                return lid
        return synthetic.get((t["symbol"], float(t.get("rate", -1)), float(t["quantity"])))

    def historical_lot(self, uid, name, t, lots, synthetic):
        """Lote ya vencido que no esta en portfolios.json: se reconstruye desde su evento de vencimiento."""
        inst = self.instrument(t["symbol"])
        if inst is None:
            return None
        maturity = to_dt(t["date"]).date()
        qty = float(t["quantity"])
        cost = (float(t["total_mxn"]) - float(t.get("realized_pnl_mxn", 0))) / qty
        h = {"symbol": t["symbol"], "quantity": qty, "rate_at_purchase": t["rate"], "purchase_date": (maturity - timedelta(days=inst["plazo_dias"])).isoformat(),
             "maturity_date": maturity.isoformat(), "purchase_price": round(cost, 7), "nominal_value": float(inst["valor_nominal"]),
             "_estado": "vencido"}
        lid = self.import_lot(uid, name, h, lots, uid_value=uid_of(t["id"], "lote-historico"))
        if lid:
            synthetic[(t["symbol"], float(t["rate"]), qty)] = lid
            self.warn(f"{name}: se reconstruyo un lote historico vencido de {t['symbol']} desde la transaccion {t['id']}")
        return lid

    def opening_balance(self, uid, name, cash, events):
        running, low, net = 0.0, 0.0, 0.0
        for ev in events:
            t = ev["t"]
            delta = float(t["total_mxn"]) * (-1 if t["side"] == "buy" else 1)
            running += delta
            low = min(low, running)
        net = running
        deposit = max(round(cash - net, 2), round(-low, 2))
        start = (events[0]["when"] - timedelta(days=1)) if events else datetime.now(timezone.utc)
        if deposit > 0:
            self.insert("movimientos_efectivo",
                        "INSERT INTO movimientos_efectivo (uid, usuario_id, fecha_hora, tipo, monto_mxn, nota) VALUES (%s, %s, %s, 'deposito', %s, %s) "
                        "ON CONFLICT (uid) DO NOTHING RETURNING id",
                        (uuid.uuid5(NS, f"saldo-inicial:{name}"), uid, start, D(deposit),
                         "Saldo inicial migrado desde portfolios.json (efectivo final menos el neto de transacciones.json)"))
        final = round(deposit + net, 2)
        if abs(final - cash) > 0.004:  # el historial exige mas efectivo del que habia: se concilia con un retiro al final
            end = events[-1]["when"] + timedelta(seconds=1) if events else start
            self.warn(f"{name}: el efectivo del JSON (${cash}) no cuadra con su historial de transacciones (diferencia ${round(final - cash, 2)}); "
                      f"se registrara un retiro de conciliacion")
            return (cash - final, end)  # monto negativo del retiro
        return None

    def user_id(self, username):
        if not username or username == "sistema":
            return None
        row = self.uid_user(username)
        return row["id"] if row else None

    def import_event(self, uid, name, ev, lots):
        t, when = ev["t"], ev["when"]
        tuid = uid_of(t["id"], f"tx:{name}")
        if t["side"] in ("coupon", "redeem"):
            self.insert("movimientos_efectivo",
                        "INSERT INTO movimientos_efectivo (uid, usuario_id, fecha_hora, tipo, monto_mxn, lote_id, cantidad, tasa, utilidad_realizada_mxn) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (uid) DO NOTHING RETURNING id",
                        (tuid, uid, when, "cupon" if t["side"] == "coupon" else "vencimiento", D(t["total_mxn"]), ev["lot"],
                         D(t["quantity"], 6), D(t.get("rate"), 6), D(t.get("realized_pnl_mxn"))))
            return
        accion = t["type"] == "accion"
        if accion:
            self.ensure_stock(t["symbol"], t.get("name"), t.get("currency"))
        by = t.get("by", name)
        total = float(t["total_mxn"])
        tx_id = self.insert(
            "transacciones",
            "INSERT INTO transacciones (uid, usuario_id, fecha_hora, tipo_activo, lado, simbolo_accion, lote_id, cantidad, precio, moneda, "
            "tipo_cambio, tasa, total_mxn, utilidad_realizada_mxn, hecha_por, rol_de_quien_la_hizo, origen) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (uid) DO NOTHING RETURNING id",
            (tuid, uid, when, t["type"], "compra" if t["side"] == "buy" else "venta", t["symbol"] if accion else None, ev["lot"],
             D(t["quantity"], 6), D(t["price"] if accion else total / float(t["quantity"]), 7), t.get("currency", "MXN") if accion else "MXN",
             D(t.get("fx_rate", 1), 8), None if accion else D(t.get("rate"), 6), D(total), D(t.get("realized_pnl_mxn")),
             self.user_id(by), t.get("by_role", "usuario"), ORIGIN.get(t.get("origin", "cliente"), "cliente")))
        if tx_id:
            self.ex("INSERT INTO movimientos_efectivo (usuario_id, fecha_hora, tipo, monto_mxn, transaccion_id, hecho_por) VALUES (%s, %s, %s, %s, %s, %s)",
                    (uid, when, "compra" if t["side"] == "buy" else "venta", D(-total if t["side"] == "buy" else total), tx_id, self.user_id(by)))

    def import_orders(self, uid, name, orders, lots):
        for o in orders:
            inst = self.instrument(o["symbol"])
            amount = o.get("amount_mxn")
            if inst is None or not amount or amount <= 0:
                self.warn(f"{name}: la orden {o['id']} no se importa (instrumento desconocido o sin monto en pesos: era por titulos)")
                continue
            if o.get("source") == "reinversión":
                lot = lots.get(str(o["source_lot_id"])) if o.get("source_lot_id") else None
                if lot:
                    origin, lote, mov = "reinversion_vencimiento", lot[0], None
                else:
                    mov_row = None
                    if not o.get("source_lot_id"):
                        mov_row = self.one("SELECT id FROM movimientos_efectivo WHERE usuario_id = %s AND tipo = 'cupon' AND monto_mxn = %s "
                                           "ORDER BY fecha_hora DESC LIMIT 1", (uid, D(amount)))
                    if not mov_row:
                        self.warn(f"{name}: la orden de reinversion {o['id']} no se puede enlazar a su lote o cupon de origen y se omite")
                        continue
                    origin, lote, mov = "reinversion_cupon", None, mov_row["id"]
            else:
                origin, lote, mov = "compra", None, None
            status = ORDER_STATUS.get(o["status"], "pendiente")
            created = to_dt(o["created_at"])
            self.insert(
                "ordenes_bono",
                "INSERT INTO ordenes_bono (uid, usuario_id, subasta_id, origen, monto_mxn, reinversion_modo, lote_origen_id, movimiento_origen_id, "
                "estado, motivo_fallo, creada_en, ejecutada_en, cancelada_en) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (uid) DO NOTHING RETURNING id",
                (uid_of(o["id"], f"orden:{name}"), uid, self.auction(o["symbol"], o["scheduled_date"], inst), origin, D(amount),
                 REINV.get(o.get("reinvest", "none"), "ninguna"), lote, mov, status, o.get("failure_reason"), created,
                 to_dt(to_date(o["scheduled_date"]) + timedelta(days=SETTLEMENT_DAYS)) if status == "ejecutada" else None,
                 created if status == "cancelada" else None))

    def notifications(self):
        for owner, items in self.load("notifications.json", {}).items():
            client = self.uid_user(owner)
            if not client:
                self.warn(f"notifications.json: el destinatario '{owner}' no existe; {len(items)} avisos omitidos")
                continue
            for n in items:
                sender = self.user_id(n.get("from"))
                if n.get("from") not in (None, "sistema") and sender is None:
                    self.warn(f"notifications.json: el remitente '{n['from']}' del aviso {n['id']} no existe; queda como aviso del sistema")
                when = to_dt(n["date"])
                self.insert("avisos",
                            "INSERT INTO avisos (uid, cliente_id, de_usuario_id, tipo, titulo, mensaje, fecha_hora, leido, leido_en) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (uid) DO NOTHING RETURNING id",
                            (uid_of(n["id"], f"aviso:{owner}"), client["id"], sender, n.get("kind", "aviso") if n.get("kind") in ("aviso", "riesgo", "accion", "alerta") else "aviso",
                             n["title"][:150], n["message"], when, bool(n.get("read")), when if n.get("read") else None))

    def plan(self):
        for owner, items in self.load("goals.json", {}).items():
            client = self.uid_user(owner)
            for g in items if client else []:
                self.insert("metas", "INSERT INTO metas (uid, cliente_id, titulo, monto_objetivo, fecha_objetivo, creada_en) "
                            "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (uid) DO NOTHING RETURNING id",
                            (uid_of(g["id"], f"meta:{owner}"), client["id"], g["title"][:150], D(g["target_mxn"]),
                             to_date(g["target_date"]) if g.get("target_date") else None, to_dt(g["date"])))
        for owner, items in self.load("notes.json", {}).items():
            client = self.uid_user(owner)
            for n in items if client else []:
                self.insert("notas", "INSERT INTO notas (uid, cliente_id, autor_id, privada, texto, fecha_hora) VALUES (%s, %s, %s, FALSE, %s, %s) "
                            "ON CONFLICT (uid) DO NOTHING RETURNING id", (uid_of(n["id"], f"nota:{owner}"), client["id"], client["id"], n["text"], to_dt(n["date"])))
        for key, items in self.load("consultant_notes.json", {}).items():
            author, _, owner = key.partition("/")
            a, client = self.uid_user(author), self.uid_user(owner)
            if not a or not client:
                self.warn(f"consultant_notes.json: la llave '{key}' no corresponde a usuarios existentes; {len(items)} notas omitidas")
                continue
            for n in items:
                self.insert("notas", "INSERT INTO notas (uid, cliente_id, autor_id, privada, texto, fecha_hora) VALUES (%s, %s, %s, TRUE, %s, %s) "
                            "ON CONFLICT (uid) DO NOTHING RETURNING id", (uid_of(n["id"], f"notaprivada:{key}"), client["id"], a["id"], n["text"], to_dt(n["date"])))
        for owner, items in self.load("alerts.json", {}).items():
            client = self.uid_user(owner)
            for a in items if client else []:
                author = self.uid_user(a["by"])
                if not author:
                    self.warn(f"alerts.json: el autor '{a['by']}' de la alerta {a['id']} no existe; se omite")
                    continue
                self.insert("alertas",
                            "INSERT INTO alertas (uid, cliente_id, creada_por, rol_creador, simbolo, tipo, porcentaje, indicacion, nivel, nivel_desde, creada_en) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (uid) DO NOTHING RETURNING id",
                            (uid_of(a["id"], f"alerta:{owner}"), client["id"], author["id"], a.get("by_role", "usuario"), a["symbol"],
                             "perdida" if a["kind"] == "loss" else "ganancia", D(a["percent"]), a.get("indication", "aviso"), a.get("level", 0),
                             to_dt(a["level_at"]) if a.get("level_at") else None, to_dt(a["date"])))
        for owner, items in self.load("signals.json", {}).items():
            client = self.uid_user(owner)
            for key, s in (items if client else {}).items():
                self.ensure_stock(s["symbol"], s["symbol"], None) if s.get("symbol") else None
                exists = self.one("SELECT 1 AS x FROM sugerencias WHERE cliente_id = %s AND clave = %s AND COALESCE(simbolo, '') = %s AND vista_por_primera_vez = %s",
                                  (client["id"], s["id"], s.get("symbol") or "", to_dt(s["first_seen"])))
                if exists:
                    self.count["sugerencias: ya existian"] += 1
                    continue
                self.ex("INSERT INTO sugerencias (cliente_id, clave, simbolo, severidad, titulo, detalle, vista_por_primera_vez, resuelta_en) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (client["id"], s["id"], s.get("symbol"), s["severity"], s["title"][:150], s["detail"], to_dt(s["first_seen"]),
                         to_dt(s["resolved_at"]) if s.get("resolved_at") else None))
                self.count["sugerencias: importados"] += 1

    def audit(self):
        for e in self.load("audit.json", []):
            admin, client = self.user_id(e.get("admin")), self.user_id(e.get("client"))
            when = to_dt(e["date"])
            after = {"symbol": e.get("symbol"), "quantity": e.get("quantity"), "asset_type": e.get("asset_type"), "client": e.get("client")}
            if self.one("SELECT 1 AS x FROM auditoria_general WHERE fecha_hora = %s AND usuario_id IS NOT DISTINCT FROM %s AND accion = %s AND despues = %s::jsonb",
                        (when, admin, e["action"], json.dumps(after))):
                self.count["auditoria: ya existian"] += 1
                continue
            self.ex("INSERT INTO auditoria_general (fecha_hora, usuario_id, cliente_id, accion, objeto_tipo, despues) VALUES (%s, %s, %s, %s, 'transacciones', %s)",
                    (when, admin, client, e["action"], Jsonb(after)))
            self.count["auditoria: importados"] += 1

    def run(self):
        for step in (self.puestos, self.users, self.catalog, self.portfolios, self.notifications, self.plan, self.audit):
            step()
        return {"counts": dict(sorted(self.count.items())), "warnings": self.warnings}


def check_integrity(conn):
    """Validaciones posteriores: saldo = suma de movimientos y sin huerfanos."""
    problems = []
    for r in conn.execute("SELECT usuario, efectivo_mxn, suma_movimientos FROM v_conciliacion_efectivo WHERE diferencia <> 0").fetchall():
        problems.append(f"{r['usuario']}: efectivo {r['efectivo_mxn']} != suma de movimientos {r['suma_movimientos']}")
    return problems


def connect():
    return psycopg.connect(
        host=os.environ.get("DB_HOST", "localhost"), port=os.environ.get("DB_PORT", "5432"), dbname=os.environ.get("DB_NAME", "datil_db"),
        user=os.environ.get("POSTGRES_USER", "datil_owner"), password=os.environ.get("POSTGRES_PASSWORD", ""),
        options="-c search_path=datil,public -c timezone=UTC", autocommit=True, row_factory=dict_row)


def run_import(conn, data_dir, dry_run=False):
    """Importa en una transaccion. dry_run revierte al final. Devuelve el reporte."""
    importer = Importer(conn, data_dir)
    try:
        with conn.transaction():
            report = importer.run()
            report["integrity_problems"] = check_integrity(conn)
            if report["integrity_problems"]:
                raise RuntimeError("Integridad rota tras importar: " + "; ".join(report["integrity_problems"]))
            if dry_run:
                raise _DryRun(report)
    except _DryRun as dry:
        report = dry.report
        report["dry_run"] = True
    return report


class _DryRun(Exception):
    def __init__(self, report):
        super().__init__("dry run")
        self.report = report


def print_report(report):
    print("\n=== Resultado de la importacion de JSON ===")
    for key, n in report["counts"].items():
        print(f"  {key}: {n}")
    for w in report["warnings"]:
        print(f"  [AVISO] {w}")
    if report.get("dry_run"):
        print("  (simulacro: no se guardo nada)")
    print("  Integridad:", "OK" if not report["integrity_problems"] else report["integrity_problems"])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=str(Path(__file__).resolve().parents[2] / "data"))
    parser.add_argument("--dry-run", action="store_true", help="simula y revierte")
    parser.add_argument("--report", help="guarda el reporte JSON en esta ruta")
    args = parser.parse_args()
    with connect() as conn:
        report = run_import(conn, args.data_dir, args.dry_run)
    print_report(report)
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
