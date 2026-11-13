"""Contabilidad de acciones: costo promedio, historial y utilidad realizada.

Todo el dinero de la cartera (efectivo, costos, totales) va en pesos (MXN),
pero las acciones cotizan en la moneda de su bolsa (USD, EUR, GBP, JPY...).
Cada operacion se convierte a pesos con el tipo de cambio del momento y ese
tipo de cambio queda registrado en la tabla transacciones. Cada posicion guarda:

- currency: moneda en la que cotiza la accion.
- avg_cost: costo promedio por accion en esa moneda, para compararlo contra el
  precio de mercado sin mezclar el efecto del tipo de cambio (lo que servira
  al riesgo).
- cost_basis_mxn: pesos que costaron las acciones que aun se tienen; con esto
  la ganancia en pesos incluye lo que subio o bajo la moneda.
- cost_estimated: True si el costo no viene de una compra registrada sino de
  una estimacion (posiciones anteriores a este esquema, ver ensure_cost).

Son funciones puras sobre el dict de la cartera: no leen ni escriben la base (lo hace db.portfolio.portfolio_tx).
"""
import uuid
from datetime import datetime, timezone

QTY_DECIMALS = 6
# Las posiciones anteriores al campo `currency` eran todas de EE.UU.
LEGACY_CURRENCY = "USD"


def find_holding(portfolio, symbol):
    return next(
        (h for h in portfolio["holdings"] if h["symbol"] == symbol and h["type"] == "accion"), None
    )


def ensure_cost(holding, price, fx_rate, currency):
    """Si la posicion no trae costo (compra anterior a este esquema), lo estima
    con el precio de hoy y lo marca como estimado: la ganancia de esa posicion
    cuenta desde hoy, no desde su compra real, y la interfaz lo avisa."""
    holding.setdefault("currency", currency)
    if holding.get("avg_cost") is not None and holding.get("cost_basis_mxn") is not None:
        return False
    holding["avg_cost"] = round(price, 4)
    holding["cost_basis_mxn"] = round(price * fx_rate * holding["quantity"], 2)
    holding["cost_estimated"] = True
    return True


def _transaction(side, symbol, name, quantity, price, currency, fx_rate, total_mxn, realized_pnl_mxn=None):
    transaction = {
        "id": str(uuid.uuid4()),
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "type": "accion",
        "side": side,
        "symbol": symbol,
        "name": name,
        "quantity": quantity,
        "price": round(price, 4),
        "currency": currency,
        "fx_rate": round(fx_rate, 8),  # monedas "chicas" (KRW, JPY) necesitan mas decimales para poder reconstruir el total
        "total_mxn": total_mxn,
    }
    if realized_pnl_mxn is not None:
        transaction["realized_pnl_mxn"] = realized_pnl_mxn
    return transaction


def buy(portfolio, symbol, name, quantity, price, currency, fx_rate):
    """Descuenta el costo en pesos y actualiza el costo promedio ponderado.
    `price` esta en `currency` y `fx_rate` son pesos por unidad de esa moneda.
    Devuelve (transaccion, error)."""
    cost_mxn = round(price * fx_rate * quantity, 2)
    if cost_mxn <= 0:
        return None, "El importe de la operación es demasiado pequeño"
    if portfolio["cash"] < cost_mxn:
        return None, "Fondos insuficientes"

    portfolio["cash"] = round(portfolio["cash"] - cost_mxn, 2)
    holding = find_holding(portfolio, symbol)

    if holding is None:
        portfolio["holdings"].append({
            "symbol": symbol,
            "name": name,
            "type": "accion",
            "currency": currency,
            "quantity": quantity,
            "avg_cost": round(price, 4),
            "cost_basis_mxn": cost_mxn,
            "cost_estimated": False,
        })
    else:
        ensure_cost(holding, price, fx_rate, currency)
        new_quantity = round(holding["quantity"] + quantity, QTY_DECIMALS)
        total_cost = holding["avg_cost"] * holding["quantity"] + price * quantity
        holding["avg_cost"] = round(total_cost / new_quantity, 4)
        holding["cost_basis_mxn"] = round(holding["cost_basis_mxn"] + cost_mxn, 2)
        holding["quantity"] = new_quantity

    return _transaction("buy", symbol, name, quantity, price, currency, fx_rate, cost_mxn), None


def sell(portfolio, symbol, quantity, price, currency, fx_rate):
    """Abona lo vendido en pesos y calcula la utilidad realizada contra el
    costo promedio de lo que se vende. Devuelve (transaccion, error)."""
    holding = find_holding(portfolio, symbol)
    if holding is None or holding["quantity"] < quantity:
        return None, "No tienes suficiente cantidad para vender"

    ensure_cost(holding, price, fx_rate, currency)
    proceeds_mxn = round(price * fx_rate * quantity, 2)
    if proceeds_mxn <= 0:
        return None, "El importe de la operación es demasiado pequeño"
    cost_sold = round(holding["cost_basis_mxn"] * (quantity / holding["quantity"]), 2)

    holding["cost_basis_mxn"] = round(holding["cost_basis_mxn"] - cost_sold, 2)
    holding["quantity"] = round(holding["quantity"] - quantity, QTY_DECIMALS)
    if holding["quantity"] == 0:
        portfolio["holdings"].remove(holding)

    portfolio["cash"] = round(portfolio["cash"] + proceeds_mxn, 2)
    transaction = _transaction(
        "sell", symbol, holding["name"], quantity, price, currency, fx_rate, proceeds_mxn,
        realized_pnl_mxn=round(proceeds_mxn - cost_sold, 2),
    )
    return transaction, None


def valuation(holding, price, fx_rate):
    """Valor de mercado en la moneda de la accion y en pesos, y ganancia
    contra el costo en pesos."""
    value_native = price * holding["quantity"]
    value_mxn = round(value_native * fx_rate, 2)
    cost = holding.get("cost_basis_mxn")

    gain_mxn = gain_percent = None
    if cost:
        gain_mxn = round(value_mxn - cost, 2)
        gain_percent = round(gain_mxn / cost * 100, 2)

    return {
        "value_native": round(value_native, 2),
        "value": value_mxn,
        "gain_mxn": gain_mxn,
        "gain_percent": gain_percent,
    }
