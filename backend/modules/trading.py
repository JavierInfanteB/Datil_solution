"""Compra y venta de acciones/bonos.

Las acciones no tienen catalogo fijo: cualquier simbolo valido de Yahoo
Finance (de cualquier bolsa del mundo) se puede comprar, y /search ayuda a
encontrarlo por nombre. Todo el dinero entra y sale en pesos: la accion se
convierte desde la moneda de su bolsa (ver utils/stock_engine). Los
bonos/CETES si son un catalogo curado (necesitan un series_id de Banxico)
y solo se subastan un dia fijo a la semana: comprar otro dia agenda una
orden pendiente en vez de ejecutarse de inmediato (ver utils/bond_engine).
"""

from flask import Blueprint, g, jsonify, request

from utils import audit, bond_engine, bond_math, stock_engine
from utils.data_store import read_json, write_json
from utils.decorators import acting_username, has_permission, require_auth, require_permission
from utils.market_data import get_bond_curve, get_current_price, get_fx_to_mxn, list_bonds, search_stocks

trading_bp = Blueprint("trading", __name__, url_prefix="/api/trading")


def _log_transaction(username, transaction):
    transactions = read_json("transactions.json")
    transactions.setdefault(username, []).append(audit.tag(transaction))
    write_json("transactions.json", transactions)


@trading_bp.route("/bonds", methods=["GET"])
@require_auth
@require_permission("trading")
def get_bonds_catalog():
    return jsonify(list_bonds())


@trading_bp.route("/search", methods=["GET"])
@require_auth
@require_permission("trading")
def search_available_stocks():
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify([])

    try:
        return jsonify(search_stocks(query))
    except Exception:
        return jsonify({"error": "No se pudo completar la búsqueda"}), 502


@trading_bp.route("/orders", methods=["GET"])
@require_auth
@require_permission("trading")
def get_orders():
    username, error = acting_username()
    if error:
        return error
    bond_engine.process_due_events(username)
    return jsonify(bond_engine.list_orders(username))


@trading_bp.route("/orders/<order_id>/cancel", methods=["POST"])
@require_auth
@require_permission("trading")
def cancel_order(order_id):
    username, error = acting_username()
    if error:
        return error
    order, error = bond_engine.cancel_order(username, order_id)
    if error:
        return jsonify({"error": error}), 400
    return jsonify(order)


@trading_bp.route("/transactions", methods=["GET"])
@require_auth
@require_permission("trading")
def get_transactions():
    username, error = acting_username()
    if error:
        return error
    transactions = read_json("transactions.json").get(username, [])
    return jsonify(sorted(transactions, key=lambda t: t["date"], reverse=True))


def _positive(value):
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value > 0


def _validate_order(body, action):
    symbol = (body.get("symbol") or "").strip().upper()
    quantity = body.get("quantity")
    amount = body.get("amount_mxn")
    asset_type = body.get("asset_type") if body.get("asset_type") in ("accion", "bono") else "accion"
    name = body.get("name") or symbol

    # Los bonos se compran por monto (como en cetesdirecto) y se venden por titulos; las acciones, por titulos.
    by_amount = asset_type == "bono" and action == "buy"
    if not symbol or not _positive(amount if by_amount else quantity):
        return None, (jsonify({"error": "Símbolo y monto válidos son requeridos" if by_amount
                               else "Símbolo y cantidad válidos son requeridos"}), 400)
    if by_amount and amount < bond_math.MIN_INVESTMENT:
        return None, (jsonify({"error": f"El monto mínimo de compra es ${bond_math.MIN_INVESTMENT}"}), 400)

    if asset_type == "bono" and symbol not in {b["symbol"] for b in list_bonds()}:
        return None, (jsonify({"error": "Bono no disponible"}), 404)

    # Cada tipo de activo es una seccion del modulo: comprar bonos pide "trading.bono".
    if not has_permission(g.current_user, f"trading.{asset_type}"):
        return None, (jsonify({"error": "Permiso denegado"}), 403)

    reinvest = body.get("reinvest") or "none"
    if reinvest not in bond_engine.REINVEST_MODES:
        return None, (jsonify({"error": "Reinversión inválida"}), 400)

    return {"symbol": symbol, "quantity": None if by_amount else quantity, "amount_mxn": amount if by_amount else None,
            "asset_type": asset_type, "name": name, "reinvest": reinvest}, None


@trading_bp.route("/buy", methods=["POST"])
@require_auth
@require_permission("trading")
def buy_asset():
    order, error = _validate_order(request.get_json(silent=True) or {}, "buy")
    if error:
        return error
    audit.record_admin_trade(request.path.rsplit("/", 1)[-1], order)

    username, error = acting_username()
    if error:
        return error
    bond_engine.process_due_events(username)

    if order["asset_type"] == "bono":
        bond = next(b for b in list_bonds() if b["symbol"] == order["symbol"])
        pending = bond_engine.schedule_purchase(username, bond, order["name"], order["amount_mxn"], order["reinvest"])
        return jsonify({
            "message": (
                f"Orden registrada para la subasta del {pending['scheduled_date']} (se liquida dos días después). "
                f"Ten el dinero en tu cuenta ese día; puedes cancelarla hasta el día anterior"
            ),
            "order": pending,
        })

    try:
        price_data = get_current_price(order["symbol"], order["asset_type"])
        fx_rate = get_fx_to_mxn(price_data["currency"])
    except Exception:
        return jsonify({"error": "No se pudo obtener el precio actual"}), 502

    portfolios = read_json("portfolios.json")
    portfolio = portfolios.setdefault(username, {"cash": 0, "holdings": []})

    transaction, err = stock_engine.buy(
        portfolio, order["symbol"], order["name"], order["quantity"],
        price_data["price"], price_data["currency"], fx_rate,
    )
    if err:
        return jsonify({"error": err}), 400

    write_json("portfolios.json", portfolios)
    _log_transaction(username, transaction)
    return jsonify({"message": "Compra realizada", "cash": portfolio["cash"], "transaction": transaction})


@trading_bp.route("/sell", methods=["POST"])
@require_auth
@require_permission("trading")
def sell_asset():
    order, error = _validate_order(request.get_json(silent=True) or {}, "sell")
    if error:
        return error
    audit.record_admin_trade(request.path.rsplit("/", 1)[-1], order)

    username, error = acting_username()
    if error:
        return error
    bond_engine.process_due_events(username)
    portfolios = read_json("portfolios.json")
    portfolio = portfolios.setdefault(username, {"cash": 0, "holdings": []})

    if order["asset_type"] == "bono":
        # Se vende a precio de mercado: sin la tasa de hoy no hay precio justo.
        try:
            curve = get_bond_curve()
            proceeds, pnl, events, err = bond_engine.sell_bond_lots(
                portfolio, order["symbol"], order["quantity"], curve
            )
        except Exception:
            return jsonify({"error": "No se pudo obtener la tasa de mercado para valuar la venta"}), 502
        if err:
            return jsonify({"error": err}), 400
        write_json("portfolios.json", portfolios)
        for event in events:
            _log_transaction(username, event)
        return jsonify({
            "message": "Venta realizada a precio de mercado",
            "cash": portfolio["cash"],
            "proceeds": proceeds,
            "realized_pnl_mxn": pnl,
        })

    holding = stock_engine.find_holding(portfolio, order["symbol"])
    if not holding or holding["quantity"] < order["quantity"]:
        return jsonify({"error": "No tienes suficiente cantidad para vender"}), 400

    try:
        price_data = get_current_price(order["symbol"], order["asset_type"])
        fx_rate = get_fx_to_mxn(price_data["currency"])
    except Exception:
        return jsonify({"error": "No se pudo obtener el precio actual"}), 502

    transaction, err = stock_engine.sell(
        portfolio, order["symbol"], order["quantity"],
        price_data["price"], price_data["currency"], fx_rate,
    )
    if err:
        return jsonify({"error": err}), 400

    write_json("portfolios.json", portfolios)
    _log_transaction(username, transaction)
    return jsonify({"message": "Venta realizada", "cash": portfolio["cash"], "transaction": transaction})


@trading_bp.route("/lots/<lot_id>/reinvest", methods=["POST"])
@require_auth
@require_permission("trading.bono")
def set_lot_reinvest(lot_id):
    """Que pasa con un lote de bonos al vencer: no reinvertir, reinvertir capital y ganancia, o la misma cantidad."""
    mode = (request.get_json(silent=True) or {}).get("mode")
    if mode not in bond_engine.REINVEST_MODES:
        return jsonify({"error": "Reinversión inválida"}), 400
    username, error = acting_username()
    if error:
        return error
    portfolios = read_json("portfolios.json")
    error = bond_engine.set_lot_reinvest(portfolios.get(username, {"holdings": []}), lot_id, mode)
    if error:
        return jsonify({"error": error}), 400
    write_json("portfolios.json", portfolios)
    return jsonify({"lot_id": lot_id, "mode": mode})


@trading_bp.route("/bonds/<symbol>/quote", methods=["GET"])
@require_auth
@require_permission("trading.bono")
def quote_bond_sale(symbol):
    """Lo que se recibiria hoy por vender `quantity` titulos, antes de confirmar la venta."""
    quantity = request.args.get("quantity", type=float)
    if not quantity or quantity <= 0:
        return jsonify({"error": "Cantidad inválida"}), 400
    username, error = acting_username()
    if error:
        return error
    bond_engine.process_due_events(username)
    portfolio = read_json("portfolios.json").get(username, {"cash": 0, "holdings": []})
    sellable = sum(h["quantity"] for h in bond_engine.sellable_lots(portfolio, symbol.upper()))
    try:
        proceeds, pnl, error = bond_engine.quote_sale(portfolio, symbol.upper(), quantity, get_bond_curve())
    except Exception:
        return jsonify({"error": "No se pudo obtener la tasa de mercado para valuar la venta"}), 502
    return jsonify({"proceeds": proceeds, "realized_pnl_mxn": pnl, "sellable": sellable, "error": error})
