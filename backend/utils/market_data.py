"""Punto unico de acceso a precios/tasas actuales e historicos.

Los modulos de negocio (dashboard, portfolio, trading, history) solo hablan
con este archivo. Las acciones aceptan cualquier simbolo valido de Yahoo
Finance (no hay catalogo fijo); los bonos si estan restringidos al catalogo
curado de series de Banxico en assets.json, porque cada uno requiere un
series_id especifico que no se puede "buscar" igual que un ticker.
"""
from utils import banxico_api, yahoo_api
from utils.data_store import read_json


def _find_bond(symbol):
    bonds = {a["symbol"]: a for a in read_json("assets.json") if a["type"] == "bono"}
    if symbol not in bonds:
        raise ValueError(f"Bono desconocido: {symbol}")
    return bonds[symbol]


def get_current_price(symbol, asset_type="accion"):
    if asset_type == "bono":
        asset = _find_bond(symbol)
        return banxico_api.get_bond_rate(asset["series_id"], symbol)
    return yahoo_api.get_current_price(symbol)


def get_history(symbol, asset_type="accion", days=30):
    if asset_type == "bono":
        asset = _find_bond(symbol)
        return banxico_api.get_bond_history(asset["series_id"], days=max(days, 180))
    return yahoo_api.get_history(symbol, days=days)


def search_stocks(query):
    return yahoo_api.search_symbols(query)


def list_bonds():
    return [a for a in read_json("assets.json") if a["type"] == "bono"]
