"""Resumen + tabla de gestion: acciones/bonos actuales, cantidades, precios y totales.

Todo se reporta en pesos (MXN). Las acciones cotizan en la moneda de su
bolsa: se valuan a precio de mercado y se convierten con el tipo de cambio de
hoy; ademas se muestra su costo y ganancia (ver utils/stock_engine).

Los bonos/CETES se valuan a mercado con las tasas de hoy de Banxico, igual que
una accion: es lo que se recibiria al venderlos (ver utils/bond_math). Junto al
valor de mercado se muestra el devengado y el valor al vencimiento, que es lo
que paga si se mantiene. Si Banxico no responde, el bono se valua devengado y
la fila lo indica (value_basis).
"""
from datetime import date

from flask import Blueprint, g, jsonify

from utils import bond_engine, bond_math, stock_engine
from utils.data_store import read_json
from utils.decorators import require_auth, require_permission
from utils.market_data import get_bond_curve, get_current_price, get_fx_to_mxn

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/portfolio")


@portfolio_bp.route("", methods=["GET"])
@require_auth
@require_permission("portfolio")
def get_portfolio():
    return jsonify(build_portfolio_view(g.current_user["username"]))


def build_portfolio_view(username, settle=True):
    """Cartera valuada en pesos. La usan tambien los modulos que necesitan los
    mismos numeros que ve el usuario (p. ej. el riesgo del portafolio).
    settle=False solo lee: no cobra cupones ni ejecuta ordenes pendientes (lo que
    hace falta cuando quien mira es el consultor y no el dueno de la cartera)."""
    if settle:
        bond_engine.process_due_events(username)

    portfolios = read_json("portfolios.json")
    portfolio = portfolios.get(username, {"cash": 0, "holdings": []})

    fx_rates = {}  # pesos por unidad de cada moneda, consultado una vez por moneda

    curve = None
    if any(h["type"] == "bono" for h in portfolio["holdings"]):
        try:
            curve = get_bond_curve()
        except Exception:
            pass  # sin tasas de hoy los bonos se valuan devengados

    today = date.today()
    holdings = []
    invested_total = 0
    incomplete = False
    for holding in portfolio["holdings"]:
        row = {
            "symbol": holding["symbol"],
            "name": holding["name"],
            "type": holding["type"],
            "quantity": holding["quantity"],
        }
        if holding["type"] == "bono":
            row["lot_id"] = holding.get("lot_id")
            row["kind"] = bond_math.kind_of(holding)
            row["rate_at_purchase"] = holding.get("rate_at_purchase")
            row["purchase_date"] = holding.get("purchase_date")
            row["maturity_date"] = holding.get("maturity_date")
            row["accrued_value"] = bond_math.accrued_value(holding, today)
            row["maturity_value"] = bond_math.maturity_value(holding)
            row["cost"] = bond_math.cost(holding)
            if row["kind"] == "bono_m":
                row["next_coupon_date"] = holding.get("next_coupon_date")
                row["coupons_paid"] = holding.get("coupons_paid", 0)
                row["coupon_amount"] = bond_math.coupon_amount(holding)

            row["value_basis"] = "mercado"
            try:
                if curve is None:
                    raise ValueError("Sin tasas de mercado")
                row["value"] = bond_math.market_value(holding, today, curve)
            except Exception:
                row["value"] = row["accrued_value"]
                row["value_basis"] = "devengado"
            row["gain_mxn"] = round(row["value"] - row["cost"], 2)
            row["gain_percent"] = round(row["gain_mxn"] / row["cost"] * 100, 2) if row["cost"] else None
            invested_total += row["value"]
        else:
            row["currency"] = holding.get("currency", stock_engine.LEGACY_CURRENCY)
            row["avg_cost"] = holding.get("avg_cost")
            row["cost_estimated"] = holding.get("cost_estimated", False)
            try:
                price_data = get_current_price(holding["symbol"], holding["type"])
                currency = price_data["currency"]
                if currency not in fx_rates:
                    fx_rates[currency] = get_fx_to_mxn(currency)
                row["currency"] = currency
                row["price"] = price_data["price"]
                row["change_percent"] = price_data["change_percent"]
                row["change_period"] = price_data["change_period"]
                row.update(stock_engine.valuation(holding, price_data["price"], fx_rates[currency]))
                invested_total += row["value"]
            except Exception:
                incomplete = True
                row["price"] = row["change_percent"] = row["change_period"] = None
                row["value"] = row["value_native"] = row["gain_mxn"] = row["gain_percent"] = None
        holdings.append(row)

    return {
        "holdings": holdings,
        "cash": portfolio["cash"],
        "invested_total": round(invested_total, 2),
        "portfolio_total": round(invested_total + portfolio["cash"], 2),
        "holdings_count": len(holdings),
        "currency": "MXN",
        "fx_rates": {c: round(rate, 4) for c, rate in fx_rates.items() if c != "MXN"},
        "incomplete": incomplete,
    }
