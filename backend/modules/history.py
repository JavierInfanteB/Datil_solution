"""Historicos de precio por simbolo, usados al ver el detalle de una accion/bono."""
from flask import Blueprint, jsonify, request

from utils.decorators import require_auth, require_permission
from utils.market_data import get_current_price, get_history

history_bp = Blueprint("history", __name__, url_prefix="/api/history")


@history_bp.route("/<symbol>", methods=["GET"])
@require_auth
@require_permission("trading")
def get_symbol_history(symbol):
    asset_type = request.args.get("type") if request.args.get("type") in ("accion", "bono") else "accion"

    try:
        current = get_current_price(symbol, asset_type)
        prices = get_history(symbol, asset_type)
    except Exception:
        return jsonify({"error": "No se pudo obtener el historico"}), 502

    return jsonify({"current": current, "history": prices})
