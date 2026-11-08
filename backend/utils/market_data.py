"""Punto unico de acceso a precios/tasas actuales e historicos.

Los modulos de negocio (dashboard, portfolio, trading, history) solo hablan
con este archivo. Las acciones aceptan cualquier simbolo valido de Yahoo
Finance (no hay catalogo fijo); los bonos si estan restringidos al catalogo
curado de series de Banxico en assets.json, porque cada uno requiere un
series_id especifico que no se puede "buscar" igual que un ticker.
"""

from utils import banxico_api, bond_math, calendar_mx, market_vector, yahoo_api
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


def get_fx_to_mxn(currency):
    """Pesos por unidad de la moneda de cotizacion de una accion."""
    return yahoo_api.get_fx_to_mxn(currency)


def search_stocks(query):
    return yahoo_api.search_symbols(query)


def list_bonds():
    return [a for a in read_json("assets.json") if a["type"] == "bono"]


def get_bond_curve():
    """Curva de mercado de hoy para valuar los lotes: el vector de precios 'on the run' de Banxico (mercado secundario de
    cada dia, no las tasas de la ultima subasta). Ver bond_math.curve_from_vector y utils/market_vector.py."""
    ids, values = market_vector.all_series(), {}
    for i in range(0, len(ids), 10):  # pocas series por consulta; cada grupo tiene su cache de 30 minutos
        values.update(banxico_api.get_latest_rates(ids[i:i + 10]))
    return bond_math.curve_from_vector(values)


def get_bond_auction_rate(symbol, auction_date):
    """Tasa de la subasta de Banxico del dia `auction_date`. Banxico la etiqueta con la fecha de colocacion (el jueves o
    el dia habil que lo sustituye). ValueError si ese dia no hubo subasta o aun no se publica."""
    placement = calendar_mx.placement_of_auction(auction_date)
    return banxico_api.get_rate_on(_find_bond(symbol)["series_id"], placement)


def get_bond_auction_term(symbol, auction_date):
    """Plazo real en dias de lo colocado en la subasta (serie `term_series_id` del catalogo). ValueError si no hay."""
    series_id = _find_bond(symbol).get("term_series_id")
    if not series_id:
        raise ValueError(f"{symbol} no tiene serie de plazo")
    term = int(round(banxico_api.get_rate_on(series_id, calendar_mx.placement_of_auction(auction_date))))
    if term <= 0:
        raise ValueError(f"Plazo invalido para {symbol}: {term}")
    return term
