"""Motor de compra/venta de bonos y CETES.

Banxico coloca (liquida) los jueves y subasta dos dias habiles antes, normalmente el martes (utils/calendar_mx.py). Toda compra es una
orden para la proxima subasta: se ejecuta cuando Banxico publica la tasa de esa subasta y, si ya paso la
liquidacion sin tasa, falla (ese instrumento no se subasto esa semana). Cada compra ejecutada crea un "lote"
independiente (holding) con su propia tasa; su plazo corre desde la liquidacion, porque cada subasta fija una tasa distinta.
Sigue las reglas de operacion de cetesdirecto: se compra por monto (minimo $100) para la subasta del proximo martes si
la orden se registra a mas tardar el dia habil anterior, y se cancela hasta ese dia. Se puede vender antes a precio de mercado
hasta 3 dias habiles antes del vencimiento. Al comprar se elige si al vencer se reinvierte en CETES a 28 dias (todo, o
solo el capital); esa orden queda pendiente y se cambia hasta 3 dias habiles antes del vencimiento.

Las formulas (precio a descuento de los CETES, cupones del Bono M, valor
devengado y valor de mercado) viven en utils/bond_math.py. Aqui esta lo que
mueve dinero: ejecutar ordenes, abonar cupones, redimir al vencer y vender.
Cada movimiento queda registrado en transactions.json (type "bono").
"""
import copy
import uuid
from datetime import date, datetime, timedelta, timezone

from utils import audit, bond_math, calendar_mx
from utils.data_store import read_json, write_json
from utils.market_data import get_bond_auction_rate, get_bond_auction_term, get_current_price


def _parse_date(value):
    return date.fromisoformat(value)


def next_scheduled_purchase_date(today=None):
    """Subasta a la que entra una orden de hoy: la primera cuyo dia habil anterior no ha pasado (normalmente el martes
    siguiente). Un martes ya entra a la de la semana siguiente."""
    return calendar_mx.next_registrable_auction(today or date.today())


def _auction_settling_on(day):
    """La subasta cuya colocacion es `day` (o la primera posterior, si `day` no es dia de colocacion)."""
    return calendar_mx.auction_settling_on(bond_math.to_date(day))


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
    transactions.setdefault(username, []).extend(audit.tag(e) for e in events)
    write_json("transactions.json", transactions)


def _redeem_lot(portfolio, lot, events):
    maturity = _parse_date(lot["maturity_date"])
    amount = bond_math.maturity_value(lot)
    portfolio["cash"] = round(portfolio["cash"] + amount, 2)
    portfolio["holdings"].remove(lot)
    events.append(_event("redeem", lot, lot["quantity"], amount, maturity,
                         realized_pnl=round(amount - bond_math.cost(lot), 2)))


def _pay_coupons(portfolio, lot, today, events, reinvestments):
    """Abona al efectivo cada cupon vencido de un Bono M. Si el lote reinvierte todo, el cupon va a CETES a 28 dias
    (se agrega la orden a `reinvestments`). Devuelve True si pago alguno."""
    paid = False
    last_date = min(today, _parse_date(lot["maturity_date"]))
    while _parse_date(lot["next_coupon_date"]) <= last_date:
        pay_date = _parse_date(lot["next_coupon_date"])
        amount = bond_math.coupon_amount(lot)
        portfolio["cash"] = round(portfolio["cash"] + amount, 2)
        lot["coupons_paid"] += 1
        lot["next_coupon_date"] = (pay_date + timedelta(days=lot["coupon_days"])).isoformat()
        events.append(_event("coupon", lot, lot["quantity"], amount, pay_date))
        if lot.get("reinvest") == "all":
            reinvestments.append(_new_order(bond_math.REINVEST_SYMBOL, "CETES 28 días", None, _auction_settling_on(pay_date),
                                            reinvest="all", amount_mxn=amount, source="reinversión"))
        paid = True
    return paid


def _execute_order(portfolio, order, bonds_by_symbol, events):
    bond = bonds_by_symbol.get(order["symbol"])
    if bond is None:
        return "failed", "El bono ya no esta disponible en el catalogo"

    # La tasa es la de la subasta de la orden (no la de hoy) y el plazo corre desde la liquidacion.
    auction = _parse_date(order["scheduled_date"])
    settlement = calendar_mx.placement_of_auction(auction)
    try:
        rate = get_bond_auction_rate(order["symbol"], auction)
        # El plazo real tambien lo publica Banxico por subasta (un CETE de 182 dias puede salir a 175).
        term = get_bond_auction_term(order["symbol"], auction) if bond.get("term_series_id") else None
    except ValueError:  # Banxico no tiene tasa de esa subasta
        if date.today() <= settlement:
            return "pending", None  # todavia puede publicar el resultado
        return "failed", "Banxico no subastó este instrumento esa semana o no hay tasa publicada"
    except Exception:
        return "pending", None  # sin conexion con Banxico: se reintenta

    quantity = order["quantity"]
    if order.get("amount_mxn") is not None:  # compra por monto: tantos titulos enteros como alcancen
        unit = bond_math.purchase_price(bond_math.new_lot(bond, 1, order["name"], rate, settlement, "unidad", term))  # sin redondear: el costo si se redondea
        quantity = bond_math.titles_for_amount(order["amount_mxn"], unit)  # truncado como asigna Banxico (importe en centavos)
        if order.get("source") == "reinversión" and quantity < bond_math.REINVEST_MIN_TITLES:
            return "failed", "No alcanza para 10 títulos de CETES a 28 días: el dinero queda en efectivo"
        if quantity < 1:
            return "failed", "El monto no alcanza para un título a la tasa de esa subasta: queda en efectivo"
    lot = bond_math.new_lot(bond, quantity, order["name"], rate, settlement, str(uuid.uuid4()), term)
    lot["reinvest"] = order.get("reinvest", "none")
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
    reinvestments = []  # cupones que se reinvierten
    changed = False

    for order in user_orders:  # ordenes de antes que no cayeron en dia de subasta (p. ej. en lunes): se pasan a su subasta
        auction = _parse_date(order["scheduled_date"])
        canonical = calendar_mx.auction_for_week(auction)
        if order["status"] == "pending" and auction != canonical:
            order["scheduled_date"] = canonical.isoformat()
            changed = True

    held = lambda lot_id: any(h.get("lot_id") == lot_id for h in portfolio["holdings"])

    def run_due_orders():
        ran = False
        for order in user_orders:
            if order["status"] != "pending" or _parse_date(order["scheduled_date"]) > today:
                continue
            if order.get("source_lot_id") and held(order["source_lot_id"]):
                continue  # una reinversion se paga con lo que entrega su lote: espera a que venza
            first_new = len(events)
            status, reason = _execute_order(portfolio, order, bonds_by_symbol, events)
            for event in events[first_new:]:
                event.update(by=username, by_role="usuario", origin="orden programada")
            if status != "pending":  # sigue pendiente mientras Banxico no publique la tasa
                order["status"], order["failure_reason"], ran = status, reason, True
        return ran

    changed = _sync_reinvestments(portfolio, user_orders) or changed
    changed = run_due_orders() or changed

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

        if bond_math.kind_of(lot) == "bono_m" and _pay_coupons(portfolio, lot, today, events, reinvestments):
            changed = True

        if _parse_date(lot["maturity_date"]) <= today:
            _redeem_lot(portfolio, lot, events)
            changed = True

    user_orders.extend(reinvestments)
    changed = run_due_orders() or changed  # reinversiones de lo que acaba de vencer y de los cupones
    changed = _sync_reinvestments(portfolio, user_orders) or changed  # y la siguiente de los lotes nuevos

    if changed:
        write_json("portfolios.json", portfolios)
        write_json("orders.json", orders)
        _append_transactions(username, events)


REINVEST_MODES = ("none", "all", "same")  # no reinvertir, todo (capital y ganancia) o solo el capital (la ganancia queda en efectivo)


def _new_order(symbol, name, quantity, scheduled_date, reinvest="none", amount_mxn=None, source="compra",
               source_lot_id=None, source_maturity=None):
    return {
        "source_lot_id": source_lot_id,
        "source_maturity": source_maturity,
        "id": str(uuid.uuid4()),
        "symbol": symbol,
        "name": name,
        "quantity": quantity,
        "amount_mxn": amount_mxn,
        "reinvest": reinvest,
        "source": source,
        "scheduled_date": scheduled_date.isoformat(),
        "created_at": date.today().isoformat(),
        "status": "pending",
        "failure_reason": None,
    }


def _reinvestment_terms(lot):
    """Cuanto compra en CETES a 28 dias la reinversion de un lote: todo lo que paga al vencer, o solo lo que costo."""
    mode = lot["reinvest"]
    amount = bond_math.maturity_value(lot) if mode == "all" else bond_math.cost(lot)
    return {"reinvest": mode, "amount_mxn": amount}


def _sync_reinvestments(portfolio, user_orders):
    """Cada lote que se reinvierte tiene una orden pendiente y visible de CETES a 28 dias en la subasta que liquida el
    dia que vence (el martes de esa semana); se ejecuta cuando el lote ya pago. Devuelve True si cambio algo."""
    lots = {h["lot_id"]: h for h in portfolio["holdings"] if h["type"] == "bono" and h.get("lot_id")}
    changed = False
    ordered = set()
    today = date.today().isoformat()
    for order in user_orders:
        if order["status"] != "pending" or not order.get("source_lot_id"):
            continue
        lot = lots.get(order["source_lot_id"])
        if lot is None:
            if today < order["source_maturity"]:  # el lote ya no esta y no ha vencido: se vendio antes
                order["status"], order["failure_reason"], changed = "cancelled", "Se vendió el lote antes de vencer", True
            continue  # si ya vencio, la orden espera su ejecucion tal como esta
        ordered.add(lot["lot_id"])
        if lot.get("reinvest", "none") == "none":
            order["status"], order["failure_reason"], changed = "cancelled", None, True
            continue
        terms = _reinvestment_terms(lot)
        if any(order.get(k) != v for k, v in terms.items()):
            order.update(terms)  # cambio el modo o la cantidad del lote
            changed = True
    for lot_id, lot in lots.items():
        if lot_id in ordered or lot.get("reinvest", "none") == "none":
            continue
        terms = _reinvestment_terms(lot)
        user_orders.append(_new_order(bond_math.REINVEST_SYMBOL, "CETES 28 días", None, _auction_settling_on(lot["maturity_date"]),
                                      reinvest=terms["reinvest"], amount_mxn=terms["amount_mxn"], source="reinversión",
                                      source_lot_id=lot_id, source_maturity=lot["maturity_date"]))
        changed = True
    return changed


def schedule_purchase(username, bond, name, amount_mxn, reinvest="none"):
    """Orden de compra por monto para la proxima subasta. `reinvest` es lo que hara el lote que resulte al vencer."""
    orders = read_json("orders.json")
    order = _new_order(bond["symbol"], name, None, next_scheduled_purchase_date(), reinvest, amount_mxn=amount_mxn)
    orders.setdefault(username, []).append(order)
    write_json("orders.json", orders)
    return order


def set_lot_reinvest(portfolio, lot_id, mode, today=None):
    """Cambia que pasa con un lote al vencer, hasta 3 dias habiles antes. Devuelve un mensaje de error o None."""
    lot = next((h for h in portfolio["holdings"] if h.get("lot_id") == lot_id and h["type"] == "bono"), None)
    if lot is None:
        return "El lote no existe"
    last = bond_math.last_change_day(lot)
    if (today or date.today()) > last:
        return f"La reinversión solo se cambia hasta 3 días hábiles antes del vencimiento (el {last.isoformat()})"
    lot["reinvest"] = mode
    return None


def cancel_order(username, order_id, today=None):
    """Cancela una orden pendiente: una compra, hasta el dia anterior a su subasta; una reinversion, hasta 3 dias habiles
    antes del vencimiento de su lote (y el lote deja de reinvertirse). Devuelve (orden, error)."""
    today = today or date.today()
    orders = read_json("orders.json")
    order = next((o for o in orders.get(username, []) if o["id"] == order_id), None)
    if order is None or order["status"] != "pending":
        return None, "La orden no existe o ya no se puede cancelar"

    if order.get("source_lot_id"):
        portfolios = read_json("portfolios.json")
        error = set_lot_reinvest(portfolios.get(username, {"holdings": []}), order["source_lot_id"], "none", today)
        if error == "El lote no existe":
            error = "El lote ya venció: la reinversión está en curso"
        if error:
            return None, error
        write_json("portfolios.json", portfolios)
    elif order.get("source") == "reinversión":
        return None, "La reinversión de un cupón ya está en curso"
    elif today >= _parse_date(order["scheduled_date"]):
        return None, "Una compra solo se cancela hasta el día anterior a su subasta"

    order["status"] = "cancelled"
    write_json("orders.json", orders)
    return order, None


def list_orders(username):
    orders = read_json("orders.json")
    return sorted(orders.get(username, []), key=lambda o: o["created_at"], reverse=True)


def sellable_lots(portfolio, symbol, today=None):
    """Lotes de `symbol` que todavia se pueden vender: hasta 3 dias habiles antes de vencer."""
    today = today or date.today()
    return [h for h in portfolio["holdings"]
            if h["symbol"] == symbol and h["type"] == "bono" and today <= bond_math.last_change_day(h)]


def quote_sale(portfolio, symbol, quantity, curve):
    """Lo que se recibiria hoy por vender: (ingreso, utilidad, error). No toca la cartera."""
    proceeds, pnl, _, error = sell_bond_lots(copy.deepcopy(portfolio), symbol, quantity, curve)
    return proceeds, pnl, error


def sell_bond_lots(portfolio, symbol, quantity, curve, today=None):
    """Vende `quantity` titulos de `symbol` con FIFO entre lotes, a precio de
    mercado de hoy (bond_math.market_value): si las tasas subieron desde la
    compra se recibe menos que lo devengado, y si bajaron, mas. Un Bono M se
    vende con su cupon corrido incluido.
    Devuelve (ingreso, utilidad realizada, movimientos, error)."""
    today = today or date.today()
    lots = sellable_lots(portfolio, symbol, today)
    available = sum(lot["quantity"] for lot in lots)

    if available < quantity:
        held = sum(h["quantity"] for h in portfolio["holdings"] if h["symbol"] == symbol and h["type"] == "bono")
        if held >= quantity:
            return None, None, None, (f"Solo puedes vender {available:g} títulos: lo que vence en menos de 3 días hábiles "
                                      "ya no se puede vender")
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
