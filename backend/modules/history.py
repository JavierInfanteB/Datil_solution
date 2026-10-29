"""Historicos de precio por simbolo, usados al ver el detalle de una accion/bono."""
from flask import Blueprint, jsonify, request

from utils.decorators import require_auth, require_permission
from utils.market_data import get_current_price, get_fx_to_mxn, get_history

history_bp = Blueprint("history", __name__, url_prefix="/api/history")

DEFAULT_DAYS = 30
MAX_DAYS = 730  # el rango mas largo que pide el front (1 ano) mas el cierre previo que le sirve de base


@history_bp.route("/<symbol>", methods=["GET"])
@require_auth
@require_permission("trading")
def get_symbol_history(symbol):
    asset_type = request.args.get("type") if request.args.get("type") in ("accion", "bono") else "accion"
    days = min(max(request.args.get("days", DEFAULT_DAYS, type=int), 1), MAX_DAYS)

    try:
        current = get_current_price(symbol, asset_type)
        prices = get_history(symbol, asset_type, days=days)
    except Exception:
        return jsonify({"error": "No se pudo obtener el histórico"}), 502

    # Las acciones cotizan en la moneda de su bolsa: el front necesita el tipo
    # de cambio para estimar el costo en pesos. Si falla, solo se muestra el
    # precio en su moneda.
    fx_mxn = None
    if asset_type == "accion":
        try:
            fx_mxn = round(get_fx_to_mxn(current["currency"]), 6)
        except Exception:
            pass

    return jsonify({"current": current, "history": prices, "fx_mxn": fx_mxn})
