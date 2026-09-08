"""Compra y venta de acciones/bonos.

Las acciones no tienen catalogo fijo: cualquier simbolo valido de Yahoo
Finance se puede comprar, y /search ayuda a encontrarlo por nombre. Los
bonos/CETES si son un catalogo curado (necesitan un series_id de Banxico)
y solo se subastan un dia fijo a la semana: comprar otro dia agenda una
orden pendiente en vez de ejecutarse de inmediato (ver utils/bond_engine).
"""
from datetime import date

from flask import Blueprint, g, jsonify, request

from utils import bond_engine
from utils.data_store import read_json, write_json
from utils.decorators import require_auth, require_permission
from utils.market_data import get_current_price, list_bonds, search_stocks

trading_bp = Blueprint("trading", __name__, url_prefix="/api/trading")


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
        return jsonify({"error": "No se pudo completar la busqueda"}), 502


@trading_bp.route("/orders", methods=["GET"])
@require_auth
@require_permission("trading")
def get_orders():
    username = g.current_user["username"]
    bond_engine.process_due_events(username)
    return jsonify(bond_engine.list_orders(username))


@trading_bp.route("/orders/<order_id>/cancel", methods=["POST"])
@require_auth
@require_permission("trading")
def cancel_order(order_id):
    order = bond_engine.cancel_order(g.current_user["username"], order_id)
    if order is None:
        return jsonify({"error": "La orden no existe o ya no se puede cancelar"}), 404
    return jsonify(order)


def _validate_order(body):
    symbol = (body.get("symbol") or "").strip().upper()
    quantity = body.get("quantity")
    asset_type = body.get("asset_type") if body.get("asset_type") in ("accion", "bono") else "accion"
    name = body.get("name") or symbol

    if not symbol or not isinstance(quantity, (int, float)) or quantity <= 0:
        return None, (jsonify({"error": "Simbolo y cantidad validos son requeridos"}), 400)

    if asset_type == "bono" and symbol not in {b["symbol"] for b in list_bonds()}:
        return None, (jsonify({"error": "Bono no disponible"}), 404)

    return {"symbol": symbol, "quantity": quantity, "asset_type": asset_type, "name": name}, None


@trading_bp.route("/buy", methods=["POST"])
@require_auth
@require_permission("trading")
def buy_asset():
    order, error = _validate_order(request.get_json(silent=True) or {})
    if error:
        return error

    username = g.current_user["username"]
    bond_engine.process_due_events(username)

    if order["asset_type"] == "bono":
        bond = next(b for b in list_bonds() if b["symbol"] == order["symbol"])
        scheduled_date = bond_engine.next_scheduled_purchase_date(bond)

        if scheduled_date != date.today():
            pending = bond_engine.schedule_purchase(username, bond, order["quantity"], order["name"])
            return jsonify({
                "message": (
                    f"Este bono solo se compra los lunes. "
                    f"Se agendo tu orden para el {pending['scheduled_date']}."
                ),
                "order": pending,
            })

        cash, err = bond_engine.buy_bond_now(username, bond, order["quantity"], order["name"])
        if err:
            return jsonify({"error": err}), 400
        return jsonify({"message": "Compra realizada", "cash": cash})

    try:
        price_data = get_current_price(order["symbol"], order["asset_type"])
    except Exception:
        return jsonify({"error": "No se pudo obtener el precio actual"}), 502

    cost = round(price_data["price"] * order["quantity"], 2)
    portfolios = read_json("portfolios.json")
    portfolio = portfolios.setdefault(username, {"cash": 0, "holdings": []})

    if portfolio["cash"] < cost:
        return jsonify({"error": "Fondos insuficientes"}), 400

    portfolio["cash"] = round(portfolio["cash"] - cost, 2)
    holding = next(
        (h for h in portfolio["holdings"] if h["symbol"] == order["symbol"] and h["type"] == "accion"), None
    )
    if holding:
        holding["quantity"] += order["quantity"]
    else:
        portfolio["holdings"].append({
            "symbol": order["symbol"],
            "name": order["name"],
            "type": "accion",
            "quantity": order["quantity"],
        })

    write_json("portfolios.json", portfolios)
    return jsonify({"message": "Compra realizada", "cash": portfolio["cash"]})


@trading_bp.route("/sell", methods=["POST"])
@require_auth
@require_permission("trading")
def sell_asset():
    order, error = _validate_order(request.get_json(silent=True) or {})
    if error:
        return error

    username = g.current_user["username"]
    bond_engine.process_due_events(username)
    portfolios = read_json("portfolios.json")
    portfolio = portfolios.setdefault(username, {"cash": 0, "holdings": []})

    if order["asset_type"] == "bono":
        proceeds, err = bond_engine.sell_bond_lots(portfolio, order["symbol"], order["quantity"])
        if err:
            return jsonify({"error": err}), 400
        write_json("portfolios.json", portfolios)
        return jsonify({
            "message": "Venta realizada (rendimiento prorrateado por los dias que se mantuvo)",
            "cash": portfolio["cash"],
        })

    holding = next(
        (h for h in portfolio["holdings"] if h["symbol"] == order["symbol"] and h["type"] == "accion"), None
    )
    if not holding or holding["quantity"] < order["quantity"]:
        return jsonify({"error": "No tienes suficiente cantidad para vender"}), 400

    try:
        price_data = get_current_price(order["symbol"], order["asset_type"])
    except Exception:
        return jsonify({"error": "No se pudo obtener el precio actual"}), 502

    proceeds = round(price_data["price"] * order["quantity"], 2)
    holding["quantity"] -= order["quantity"]
    if holding["quantity"] == 0:
        portfolio["holdings"].remove(holding)
    portfolio["cash"] = round(portfolio["cash"] + proceeds, 2)

    write_json("portfolios.json", portfolios)
    return jsonify({"message": "Venta realizada", "cash": portfolio["cash"]})
