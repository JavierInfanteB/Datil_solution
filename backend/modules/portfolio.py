"""Resumen + tabla de gestion: acciones/bonos actuales, cantidades, precios y totales.

Las acciones se valuan a precio de mercado. Los bonos/CETES ya comprados NO
se re-cotizan contra Banxico: su valor es el devengado (principal + interes
acumulado a hoy segun la tasa que se fijo al comprarlos), porque la tasa de
un bono ya adquirido no cambia con el mercado.
"""
from flask import Blueprint, g, jsonify

from utils import bond_engine
from utils.data_store import read_json
from utils.decorators import require_auth, require_permission
from utils.market_data import get_current_price

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/portfolio")


@portfolio_bp.route("", methods=["GET"])
@require_auth
@require_permission("portfolio")
def get_portfolio():
    username = g.current_user["username"]
    bond_engine.process_due_events(username)

    portfolios = read_json("portfolios.json")
    portfolio = portfolios.get(username, {"cash": 0, "holdings": []})

    holdings = []
    invested_total = 0
    for holding in portfolio["holdings"]:
        row = {
            "symbol": holding["symbol"],
            "name": holding["name"],
            "type": holding["type"],
            "quantity": holding["quantity"],
        }
        if holding["type"] == "bono":
            row["rate_at_purchase"] = holding.get("rate_at_purchase")
            row["purchase_date"] = holding.get("purchase_date")
            row["maturity_date"] = holding.get("maturity_date")
            row["value"] = bond_engine.estimate_lot_value(holding)
            invested_total += row["value"]
        else:
            try:
                price_data = get_current_price(holding["symbol"], holding["type"])
                row["price"] = price_data["price"]
                row["change_percent"] = price_data["change_percent"]
                row["change_period"] = price_data["change_period"]
                row["value"] = round(price_data["price"] * holding["quantity"], 2)
                invested_total += row["value"]
            except Exception:
                row["price"] = row["change_percent"] = row["value"] = row["change_period"] = None
        holdings.append(row)

    return jsonify({
        "holdings": holdings,
        "cash": portfolio["cash"],
        "invested_total": round(invested_total, 2),
        "portfolio_total": round(invested_total + portfolio["cash"], 2),
        "holdings_count": len(holdings),
    })
