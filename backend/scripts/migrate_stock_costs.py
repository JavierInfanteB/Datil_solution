"""Migracion unica: asigna costo a las acciones que se compraron antes de que
la cartera guardara el costo promedio.

No hay forma de recuperar a que precio se compraron, asi que el costo se
estima con el precio y el tipo de cambio de hoy y la posicion queda marcada
con cost_estimated=true (la interfaz lo avisa). Es idempotente: las posiciones
que ya tienen costo no se tocan, y si Yahoo falla no se escribe nada.

Uso (desde backend/):  python scripts/migrate_stock_costs.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import stock_engine  # noqa: E402
from utils.data_store import read_json, write_json  # noqa: E402
from utils.market_data import get_current_price, get_fx_to_mxn  # noqa: E402


def main():
    portfolios = read_json("portfolios.json")
    pending = [
        (username, holding)
        for username, portfolio in portfolios.items()
        for holding in portfolio["holdings"]
        if holding["type"] == "accion" and holding.get("avg_cost") is None
    ]

    if not pending:
        print("Nada que migrar: todas las acciones ya tienen costo.")
        return

    for username, holding in pending:
        price_data = get_current_price(holding["symbol"], "accion")
        currency = price_data["currency"]
        fx_rate = get_fx_to_mxn(currency)
        stock_engine.ensure_cost(holding, price_data["price"], fx_rate, currency)
        print(f"{username}/{holding['symbol']}: costo estimado {holding['avg_cost']} {currency} ({currency}/MXN {fx_rate:.4f})")

    write_json("portfolios.json", portfolios)
    print(f"Listo: {len(pending)} posiciones migradas.")


if __name__ == "__main__":
    main()
