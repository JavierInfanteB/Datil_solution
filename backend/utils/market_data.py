"""Punto unico de acceso a precios/tasas actuales e historicos.

Los modulos de negocio (dashboard, portfolio, trading, history) solo hablan
con este archivo. Las acciones aceptan cualquier simbolo valido de Yahoo
Finance (no hay catalogo fijo); los bonos si estan restringidos al catalogo
curado de series de Banxico (tablas instrumentos y series_mercado), porque cada uno requiere un
series_id especifico que no se puede "buscar" igual que un ticker.
"""
from datetime import timedelta

from utils import banxico_api, bond_math, yahoo_api
from db import portfolio as pf_repo


def _find_bond(symbol):
    bonds = {b["symbol"]: b for b in list_bonds()}
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


def get_fx_to_mxn(currency):
    """Pesos por unidad de la moneda de cotizacion de una accion."""
    return yahoo_api.get_fx_to_mxn(currency)


def search_stocks(query):
    return yahoo_api.search_symbols(query)


def list_bonds():
    return pf_repo.catalog_bonds()


def get_bond_curve():
    """Tasas de mercado de hoy de todos los bonos (una consulta a Banxico),
    listas para valuar a mercado: ver bond_math.build_curve."""
    bonds = list_bonds()
    symbol_by_series = {b["series_id"]: b["symbol"] for b in bonds}
    rates = banxico_api.get_latest_rates(list(symbol_by_series))
    return bond_math.build_curve({symbol_by_series[s]: r for s, r in rates.items()}, bonds)


def get_bond_auction_rate(symbol, auction_date):
    """Tasa de la subasta de Banxico del dia `auction_date` (martes). ValueError si ese dia no hubo o aun no se publica."""
    settlement = auction_date + timedelta(days=bond_math.SETTLEMENT_DAYS)
    return banxico_api.get_rate_on(_find_bond(symbol)["series_id"], settlement)
