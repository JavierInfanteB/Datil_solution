"""Compra y venta de acciones/bonos.

Las acciones no tienen catalogo fijo: cualquier simbolo valido de Yahoo
Finance (de cualquier bolsa del mundo) se puede comprar, y /search ayuda a
encontrarlo por nombre. Todo el dinero entra y sale en pesos: la accion se
convierte desde la moneda de su bolsa (ver utils/stock_engine). Los
bonos/CETES si son un catalogo curado (necesitan un series_id de Banxico)
y solo se subastan un dia fijo a la semana: comprar otro dia agenda una
orden pendiente en vez de ejecutarse de inmediato (ver utils/bond_engine).
"""
from datetime import date

from flask import Blueprint, g, jsonify, request

from utils import bond_engine, stock_engine
from utils.data_store import read_json, write_json
from utils import audit
from utils.decorators import acting_username, has_permission, require_auth, require_permission
from utils.market_data import get_bond_curve, get_current_price, get_fx_to_mxn, list_bonds, search_stocks

trading_bp = Blueprint("trading", __name__, url_prefix="/api/trading")


def _log_transaction(username, transaction):
    transactions = read_json("transactions.json")
    transactions.setdefault(username, []).append(transaction)
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
    order = bond_engine.cancel_order(username, order_id)
    if order is None:
        return jsonify({"error": "La orden no existe o ya no se puede cancelar"}), 404
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


def _validate_order(body):
    symbol = (body.get("symbol") or "").strip().upper()
    quantity = body.get("quantity")
    asset_type = body.get("asset_type") if body.get("asset_type") in ("accion", "bono") else "accion"
    name = body.get("name") or symbol

    if not symbol or isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or quantity <= 0:
        return None, (jsonify({"error": "Símbolo y cantidad válidos son requeridos"}), 400)

    if asset_type == "bono" and symbol not in {b["symbol"] for b in list_bonds()}:
        return None, (jsonify({"error": "Bono no disponible"}), 404)

    # Cada tipo de activo es una seccion del modulo: comprar bonos pide "trading.bono".
    if not has_permission(g.current_user, f"trading.{asset_type}"):
        return None, (jsonify({"error": "Permiso denegado"}), 403)

    return {"symbol": symbol, "quantity": quantity, "asset_type": asset_type, "name": name}, None


@trading_bp.route("/buy", methods=["POST"])
@require_auth
@require_permission("trading")
def buy_asset():
    order, error = _validate_order(request.get_json(silent=True) or {})
    if error:
        return error
    audit.record_admin_trade(request.path.rsplit("/", 1)[-1], order)

    username, error = acting_username()
    if error:
        return error
    bond_engine.process_due_events(username)

    if order["asset_type"] == "bono":
        bond = next(b for b in list_bonds() if b["symbol"] == order["symbol"])
        scheduled_date = bond_engine.next_scheduled_purchase_date(bond)

        if scheduled_date != date.today():
            pending = bond_engine.schedule_purchase(username, bond, order["quantity"], order["name"])
            return jsonify({
                "message": (
                    f"Este bono solo se compra los lunes. "
                    f"Se agendó tu orden para el {pending['scheduled_date']}."
                ),
                "order": pending,
            })

        cash, err = bond_engine.buy_bond_now(username, bond, order["quantity"], order["name"])
        if err:
            return jsonify({"error": err}), 400
        return jsonify({"message": "Compra realizada", "cash": cash})

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
    order, error = _validate_order(request.get_json(silent=True) or {})
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
