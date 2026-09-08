"""Motor de compra/venta de bonos y CETES.

Los bonos solo se subastan un dia fijo a la semana (purchase_weekday en
assets.json). Si se pide comprar otro dia, se agenda una orden pendiente
para la proxima fecha habil en vez de ejecutarse de inmediato. Cada compra
ejecutada crea un "lote" independiente (holding) con su propia tasa y fecha
de vencimiento, porque cada subasta fija una tasa distinta. El rendimiento
se calcula con interes simple, convencion de 360 dias (la que usa el
mercado de dinero mexicano): interes = nominal * tasa/100 * dias/360.
"""
import uuid
from datetime import date, timedelta

from utils.data_store import read_json, write_json
from utils.market_data import get_current_price


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


def _accrued_value(lot, as_of):
    purchase_date = _parse_date(lot["purchase_date"])
    maturity_date = _parse_date(lot["maturity_date"])
    days_elapsed = max(0, min((as_of - purchase_date).days, (maturity_date - purchase_date).days))
    principal = lot["nominal_value"] * lot["quantity"]
    interest = principal * (lot["rate_at_purchase"] / 100) * (days_elapsed / 360)
    return round(principal + interest, 2), days_elapsed


def estimate_lot_value(lot, as_of=None):
    """Valor de mark-to-model de un lote: principal + interes devengado a hoy."""
    value, _ = _accrued_value(lot, as_of or date.today())
    return value


def _redeem_lot(portfolio, lot):
    value, _ = _accrued_value(lot, _parse_date(lot["maturity_date"]))
    portfolio["cash"] = round(portfolio["cash"] + value, 2)
    portfolio["holdings"].remove(lot)


def _execute_order(portfolio, order, bonds_by_symbol):
    bond = bonds_by_symbol.get(order["symbol"])
    if bond is None:
        return "failed", "El bono ya no esta disponible en el catalogo"

    try:
        rate = get_current_price(order["symbol"], "bono")["price"]
    except Exception:
        return "failed", "No se pudo obtener la tasa vigente para ejecutar la orden"

    principal = bond["nominal_value"] * order["quantity"]
    if portfolio["cash"] < principal:
        return "failed", "Fondos insuficientes al momento de ejecutar la orden"

    purchase_date = order["scheduled_date"]
    maturity_date = (_parse_date(purchase_date) + timedelta(days=bond["term_days"])).isoformat()

    portfolio["cash"] = round(portfolio["cash"] - principal, 2)
    portfolio["holdings"].append({
        "symbol": order["symbol"],
        "name": order["name"],
        "type": "bono",
        "quantity": order["quantity"],
        "nominal_value": bond["nominal_value"],
        "rate_at_purchase": rate,
        "purchase_date": purchase_date,
        "maturity_date": maturity_date,
        "lot_id": str(uuid.uuid4()),
    })
    return "executed", None


def process_due_events(username):
    """Ejecuta ordenes vencidas y redime bonos que ya llegaron a su
    vencimiento. Se llama de forma perezosa en cada lectura de cartera: para
    esta app de demostracion no hace falta un scheduler/cron aparte."""
    today = date.today()
    portfolios = read_json("portfolios.json")
    orders = read_json("orders.json")
    portfolio = portfolios.setdefault(username, {"cash": 0, "holdings": []})
    user_orders = orders.setdefault(username, [])
    bonds_by_symbol = {b["symbol"]: b for b in read_json("assets.json") if b["type"] == "bono"}

    changed = False

    for order in user_orders:
        if order["status"] != "pending" or _parse_date(order["scheduled_date"]) > today:
            continue
        order["status"], order["failure_reason"] = _execute_order(portfolio, order, bonds_by_symbol)
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
            lot.update({
                "nominal_value": bond["nominal_value"],
                "rate_at_purchase": rate,
                "purchase_date": today.isoformat(),
                "maturity_date": (today + timedelta(days=bond["term_days"])).isoformat(),
                "lot_id": str(uuid.uuid4()),
            })
            changed = True
            continue

        if _parse_date(lot["maturity_date"]) <= today:
            _redeem_lot(portfolio, lot)
            changed = True

    if changed:
        write_json("portfolios.json", portfolios)
        write_json("orders.json", orders)


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


def sell_bond_lots(portfolio, symbol, quantity):
    """Vende `quantity` titulos de `symbol` con FIFO entre lotes, prorrateando
    el rendimiento de cada lote solo por los dias que efectivamente se
    mantuvo (no se paga el rendimiento completo si se vende antes de vencer).
    """
    today = date.today()
    lots = [h for h in portfolio["holdings"] if h["symbol"] == symbol and h["type"] == "bono"]
    available = sum(lot["quantity"] for lot in lots)

    if available < quantity:
        return None, "No tienes suficientes titulos para vender"

    remaining = quantity
    proceeds = 0.0
    for lot in sorted(lots, key=lambda lot: lot["purchase_date"]):
        if remaining <= 0:
            break
        take = min(lot["quantity"], remaining)
        value, _ = _accrued_value({**lot, "quantity": take}, today)
        proceeds += value
        lot["quantity"] -= take
        remaining -= take

    portfolio["holdings"] = [h for h in portfolio["holdings"] if not (h["type"] == "bono" and h["quantity"] == 0)]
    proceeds = round(proceeds, 2)
    portfolio["cash"] = round(portfolio["cash"] + proceeds, 2)
    return proceeds, None


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

    status, reason = _execute_order(portfolio, pseudo_order, {bond["symbol"]: bond})
    if status == "failed":
        return None, reason

    write_json("portfolios.json", portfolios)
    return portfolio["cash"], None
