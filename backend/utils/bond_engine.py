"""Motor de compra/venta de bonos y CETES.

Los bonos solo se subastan un dia fijo a la semana (purchase_weekday en
assets.json). Si se pide comprar otro dia, se agenda una orden pendiente
para la proxima fecha habil en vez de ejecutarse de inmediato. Cada compra
ejecutada crea un "lote" independiente (holding) con su propia tasa y fecha
de vencimiento, porque cada subasta fija una tasa distinta.

Las formulas (precio a descuento de los CETES, cupones del Bono M, valor
devengado y valor de mercado) viven en utils/bond_math.py. Aqui esta lo que
mueve dinero: ejecutar ordenes, abonar cupones, redimir al vencer y vender.
Cada movimiento queda registrado en transactions.json (type "bono").
"""
import uuid
from datetime import date, datetime, timedelta, timezone

from utils import bond_math
from utils.data_store import read_json, write_json
from utils.market_data import get_bond_rate_at, get_current_price


def _parse_date(value):
    return date.fromisoformat(value)


def _next_weekday_on_or_after(start, weekday):
    """weekday: 0=lunes ... 6=domingo. Si start ya cae en ese dia, se usa start."""
    days_ahead = (weekday - start.weekday()) % 7
    return start + timedelta(days=days_ahead)


def next_scheduled_purchase_date(bond, today=None):
    today = today or date.today()
    if today.weekday() == bond["purchase_weekday"]:
        return today
    return _next_weekday_on_or_after(today + timedelta(days=1), bond["purchase_weekday"])


def _event(side, lot, quantity, total_mxn, event_date=None, realized_pnl=None):
    """Registro de un movimiento de bonos para transactions.json.
    side: buy | sell | coupon | redeem."""
    if event_date is None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    else:
        stamp = f"{event_date.isoformat()}T00:00:00+00:00"
    event = {
        "id": str(uuid.uuid4()),
        "date": stamp,
        "type": "bono",
        "side": side,
        "symbol": lot["symbol"],
        "name": lot["name"],
        "quantity": quantity,
        "rate": lot["rate_at_purchase"],
        "total_mxn": total_mxn,
    }
    if realized_pnl is not None:
        event["realized_pnl_mxn"] = realized_pnl
    return event


def _append_transactions(username, events):
    if not events:
        return
    transactions = read_json("transactions.json")
    transactions.setdefault(username, []).extend(events)
    write_json("transactions.json", transactions)


def _redeem_lot(portfolio, lot, events):
    maturity = _parse_date(lot["maturity_date"])
    amount = bond_math.maturity_value(lot)
    portfolio["cash"] = round(portfolio["cash"] + amount, 2)
    portfolio["holdings"].remove(lot)
    events.append(_event("redeem", lot, lot["quantity"], amount, maturity,
                         realized_pnl=round(amount - bond_math.cost(lot), 2)))


def _pay_coupons(portfolio, lot, today, events):
    """Abona al efectivo cada cupon vencido de un Bono M. Devuelve True si pago alguno."""
    paid = False
    last_date = min(today, _parse_date(lot["maturity_date"]))
    while _parse_date(lot["next_coupon_date"]) <= last_date:
        pay_date = _parse_date(lot["next_coupon_date"])
        amount = bond_math.coupon_amount(lot)
        portfolio["cash"] = round(portfolio["cash"] + amount, 2)
        lot["coupons_paid"] += 1
        lot["next_coupon_date"] = (pay_date + timedelta(days=lot["coupon_days"])).isoformat()
        events.append(_event("coupon", lot, lot["quantity"], amount, pay_date))
        paid = True
    return paid


def _execute_order(portfolio, order, bonds_by_symbol, events):
    bond = bonds_by_symbol.get(order["symbol"])
    if bond is None:
        return "failed", "El bono ya no esta disponible en el catalogo"

    # Una orden que se ejecuta con retraso (el usuario no abrio la app ese dia)
    # usa la tasa de su fecha de subasta, no la de hoy.
    scheduled = _parse_date(order["scheduled_date"])
    try:
        if scheduled < date.today():
            rate = get_bond_rate_at(order["symbol"], scheduled)
        else:
            rate = get_current_price(order["symbol"], "bono")["price"]
    except Exception:
        return "failed", "No se pudo obtener la tasa vigente para ejecutar la orden"

    lot = bond_math.new_lot(bond, order["quantity"], order["name"], rate, scheduled, str(uuid.uuid4()))
    cost = bond_math.cost(lot)
    if portfolio["cash"] < cost:
        return "failed", "Fondos insuficientes al momento de ejecutar la orden"

    portfolio["cash"] = round(portfolio["cash"] - cost, 2)
    portfolio["holdings"].append(lot)
    events.append(_event("buy", lot, lot["quantity"], cost))
    return "executed", None


def process_due_events(username):
    """Ejecuta ordenes vencidas, abona cupones del Bono M y redime lo que ya
    llego a su vencimiento. Se llama de forma perezosa en cada lectura de
    cartera: para esta app de demostracion no hace falta un scheduler/cron."""
    today = date.today()
    portfolios = read_json("portfolios.json")
    orders = read_json("orders.json")
    portfolio = portfolios.setdefault(username, {"cash": 0, "holdings": []})
    user_orders = orders.setdefault(username, [])
    bonds_by_symbol = {b["symbol"]: b for b in read_json("assets.json") if b["type"] == "bono"}

    events = []
    changed = False

    for order in user_orders:
        if order["status"] != "pending" or _parse_date(order["scheduled_date"]) > today:
            continue
        order["status"], order["failure_reason"] = _execute_order(portfolio, order, bonds_by_symbol, events)
        changed = True

    for lot in list(portfolio["holdings"]):
        if lot["type"] != "bono":
            continue

        if "maturity_date" not in lot:
            # Datos de antes de este esquema: se homologan asignando la
            # compra a hoy para que sigan el ciclo normal de vencimiento.
            bond = bonds_by_symbol.get(lot["symbol"])
            if not bond:
                continue
            try:
                rate = get_current_price(lot["symbol"], "bono")["price"]
            except Exception:
                rate = 0
            lot.update(bond_math.new_lot(bond, lot["quantity"], lot["name"], rate, today, str(uuid.uuid4())))
            changed = True
            continue

        if bond_math.kind_of(lot) == "bono_m" and _pay_coupons(portfolio, lot, today, events):
            changed = True

        if _parse_date(lot["maturity_date"]) <= today:
            _redeem_lot(portfolio, lot, events)
            changed = True

    if changed:
        write_json("portfolios.json", portfolios)
        write_json("orders.json", orders)
        _append_transactions(username, events)


def schedule_purchase(username, bond, quantity, name):
    orders = read_json("orders.json")
    user_orders = orders.setdefault(username, [])
    scheduled_date = next_scheduled_purchase_date(bond)

    order = {
        "id": str(uuid.uuid4()),
        "symbol": bond["symbol"],
        "name": name,
        "quantity": quantity,
        "scheduled_date": scheduled_date.isoformat(),
        "created_at": date.today().isoformat(),
        "status": "pending",
        "failure_reason": None,
    }
    user_orders.append(order)
    write_json("orders.json", orders)
    return order


def cancel_order(username, order_id):
    orders = read_json("orders.json")
    user_orders = orders.get(username, [])
    order = next((o for o in user_orders if o["id"] == order_id), None)

    if order is None or order["status"] != "pending":
        return None

    order["status"] = "cancelled"
    write_json("orders.json", orders)
    return order


def list_orders(username):
    orders = read_json("orders.json")
    return sorted(orders.get(username, []), key=lambda o: o["created_at"], reverse=True)


def sell_bond_lots(portfolio, symbol, quantity, curve, today=None):
    """Vende `quantity` titulos de `symbol` con FIFO entre lotes, a precio de
    mercado de hoy (bond_math.market_value): si las tasas subieron desde la
    compra se recibe menos que lo devengado, y si bajaron, mas. Un Bono M se
    vende con su cupon corrido incluido.
    Devuelve (ingreso, utilidad realizada, movimientos, error)."""
    today = today or date.today()
    lots = [h for h in portfolio["holdings"] if h["symbol"] == symbol and h["type"] == "bono"]
    available = sum(lot["quantity"] for lot in lots)

    if available < quantity:
        return None, None, None, "No tienes suficientes títulos para vender"

    remaining = quantity
    proceeds = 0.0
    total_cost = 0.0
    events = []
    for lot in sorted(lots, key=lambda lot: lot["purchase_date"]):
        if remaining <= 0:
            break
        take = min(lot["quantity"], remaining)
        piece = {**lot, "quantity": take}
        value = bond_math.market_value(piece, today, curve)
        cost = bond_math.cost(piece)
        proceeds += value
        total_cost += cost
        events.append(_event("sell", piece, take, value, realized_pnl=round(value - cost, 2)))
        lot["quantity"] = round(lot["quantity"] - take, 6)
        remaining -= take

    portfolio["holdings"] = [h for h in portfolio["holdings"] if not (h["type"] == "bono" and h["quantity"] == 0)]
    proceeds = round(proceeds, 2)
    portfolio["cash"] = round(portfolio["cash"] + proceeds, 2)
    return proceeds, round(proceeds - total_cost, 2), events, None


def buy_bond_now(username, bond, quantity, name):
    """Ejecuta la compra de inmediato: solo se debe llamar cuando ya se
    valido que hoy es el dia habil de subasta de ese bono."""
    portfolios = read_json("portfolios.json")
    portfolio = portfolios.setdefault(username, {"cash": 0, "holdings": []})
    pseudo_order = {
        "symbol": bond["symbol"],
        "name": name,
        "quantity": quantity,
        "scheduled_date": date.today().isoformat(),
    }

    events = []
    status, reason = _execute_order(portfolio, pseudo_order, {bond["symbol"]: bond}, events)
    if status == "failed":
        return None, reason

    write_json("portfolios.json", portfolios)
    _append_transactions(username, events)
    return portfolio["cash"], None
