"""Riesgo de acciones y del portafolio, y comparador de acciones.

Las reglas y formulas estan en utils/risk_engine.py (sin I/O); aqui se bajan
los historicos de Yahoo (5 anos, en cache), se llevan a pesos con el tipo de
cambio diario y se arman las respuestas. El ETF global ACWI hace de mercado de
referencia para la beta.
"""
import threading
import time
from datetime import date, timedelta

from flask import Blueprint, g, jsonify, request

from modules.portfolio import build_portfolio_view
from utils import bond_math, risk_engine, yahoo_api
from db import portfolio as pf_repo
from utils.decorators import require_auth, require_permission
from utils.market_data import get_bond_curve

risk_bp = Blueprint("risk", __name__, url_prefix="/api/risk")

BENCHMARK = "ACWI"
MAX_COMPARE = 5
CACHE_TTL_SECONDS = 6 * 60 * 60  # un cierre diario no cambia durante el dia
_cache = {}
_cache_lock = threading.Lock()


def _cached(key, loader):
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    value = loader()
    with _cache_lock:
        _cache[key] = (time.monotonic(), value)
    return value


def _to_mxn(series, fx_series):
    """Lleva una serie a pesos con el tipo de cambio del dia (o el ultimo conocido)."""
    if fx_series is None:
        return series
    out, j = [], -1
    for day, price in series:
        while j + 1 < len(fx_series) and fx_series[j + 1][0] <= day:
            j += 1
        if j >= 0:
            out.append((day, price * fx_series[j][1]))
    return out


def load_stock(symbol):
    """Historico en moneda original y en pesos, con sus datos basicos."""
    symbol = symbol.upper()

    def loader():
        data = yahoo_api.get_price_series(symbol)
        fx = yahoo_api.get_fx_series(data["currency"])
        data["series_mxn"] = _to_mxn(data["series"], fx)
        data["symbol"] = symbol
        return data

    return _cached(("stock", symbol), loader)


def _benchmark_series():
    # Misma carga (y misma entrada de cache) que cualquier accion: el benchmark tambien se usa en pesos.
    return load_stock(BENCHMARK)["series"]


MARKET_START = date(2008, 3, 1)  # el ACWI diario empieza en marzo de 2008: incluye 2008, 2020 y 2022


def market_worst():
    """Peor mes del mercado global (ACWI, USD, 21 dias habiles) desde 2008: {"return", "from", "to"} (cache de 6 h)."""
    def loader():
        series = yahoo_api.get_price_series_between(BENCHMARK, MARKET_START, date.today())
        change, start, end = risk_engine.worst_window(series)
        return {"return": change, "from": start, "to": end}
    return _cached(("market-worst",), loader)


def _stress(stock_rows, total):
    """Perdida del portafolio si el mercado repitiera su peor mes: beta del portafolio (acciones con su beta; bonos y efectivo en 0) x ese mes."""
    try:
        market = market_worst()
    except Exception as exc:
        return {"error": _describe(exc)[0]}
    covered = [r for r in stock_rows if (r.get("metrics") or {}).get("beta") is not None]
    beta = sum(r["value"] / total * r["metrics"]["beta"] for r in covered)
    loss = risk_engine.stress_loss(beta, market["return"])
    return {"market_worst_percent": round(market["return"] * 100, 1), "from": market["from"], "to": market["to"], "beta": round(beta, 2),
            "loss_percent": round(loss * 100, 2), "loss_mxn": round(loss * total, 2),
            "covers_pct_of_portfolio": round(sum(r["value"] for r in covered) / total * 100, 1)}


def assess(symbol):
    """Metricas + puntaje de riesgo de una accion."""
    data = load_stock(symbol)
    metrics = risk_engine.compute_metrics(data["series_mxn"], data["series"], _benchmark_series())
    assessment = risk_engine.score_metrics(metrics)
    return {
        "symbol": data["symbol"],
        "name": data["name"],
        "exchange": data["exchange"],
        "currency": data["currency"],
        "as_of": data["series_mxn"][-1][0],
        "metrics": {k: None if v is None else round(v, 2) for k, v in metrics.items()},
        **assessment,
    }


def _describe(exc):
    """(mensaje, codigo HTTP) para un fallo al evaluar un simbolo."""
    if isinstance(exc, ValueError) and "Historia insuficiente" in str(exc):
        return str(exc), 422
    return "No se pudo obtener el histórico de este símbolo", 502


@risk_bp.route("/stock/<symbol>", methods=["GET"])
@require_auth
@require_permission("risk")
def stock_risk(symbol):
    try:
        return jsonify(assess(symbol))
    except Exception as exc:
        message, status = _describe(exc)
        return jsonify({"error": message}), status


def _comparison_series(loaded, years=1):
    """Series en pesos base 100, desde el primer dia en que TODAS cotizan dentro
    de la ventana, con el ultimo precio conocido en los dias sin operacion."""
    cutoff = (date.today() - timedelta(days=365 * years)).isoformat()
    windows = {s: [(d, p) for d, p in data["series_mxn"] if d >= cutoff] for s, data in loaded.items()}
    start = max(w[0][0] for w in windows.values())
    days = sorted({d for w in windows.values() for d, _ in w if d >= start})

    normalized = {}
    for symbol, window in windows.items():
        by_day = dict(window)
        last = next((p for d, p in reversed(window) if d <= start), window[0][1])
        base, values = by_day.get(start, last), []
        for day in days:
            last = by_day.get(day, last)
            values.append(last / base * 100)
        normalized[symbol] = values

    return [{"date": day, **{s: round(normalized[s][i], 2) for s in normalized}} for i, day in enumerate(days)]


@risk_bp.route("/compare", methods=["GET"])
@require_auth
@require_permission("risk")
def compare():
    symbols = []
    for raw in (request.args.get("symbols") or "").split(","):
        symbol = raw.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    if len(symbols) < 2 or len(symbols) > MAX_COMPARE:
        return jsonify({"error": f"Compara entre 2 y {MAX_COMPARE} símbolos"}), 400

    assessments, loaded, failures = [], {}, {}
    for symbol in symbols:
        try:
            assessments.append(assess(symbol))
            loaded[symbol] = load_stock(symbol)
        except Exception as exc:
            failures[symbol] = _describe(exc)[0]

    if len(assessments) < 2:
        return jsonify({"error": "Se necesitan al menos 2 símbolos con historia suficiente", "failures": failures}), 422

    return jsonify({
        "assessments": assessments,
        "series": _comparison_series(loaded),
        "failures": failures,
    })


# ------------------------------------------------------------------ portafolio

def _portfolio_index(positions, weights):
    """Serie del portafolio con los pesos de hoy mantenidos constantes (lo que
    habria pasado si se tuvo siempre esta mezcla). Acciones en pesos, con el ultimo
    precio conocido los dias sin operacion; bonos y efectivo no se mueven."""
    window = {s: p["series_mxn"][-risk_engine.LONG_WINDOW - 1:] for s, p in positions.items()}
    start = max(w[0][0] for w in window.values())
    days = sorted({d for w in window.values() for d, _ in w if d >= start})
    if len(days) < risk_engine.MIN_RETURNS + 1:
        raise ValueError("Historia insuficiente en común entre las acciones del portafolio")

    filled = {}
    for symbol, w in window.items():
        by_day, last, values = dict(w), next(p for d, p in w if d >= start), []
        for day in days:
            last = by_day.get(day, last)
            values.append(last)
        filled[symbol] = values

    index, level = [], 100.0
    for i, day in enumerate(days):
        if i > 0:
            step = sum(weights[s] * (filled[s][i] / filled[s][i - 1] - 1) for s in filled)
            level *= 1 + step
        index.append((day, level))
    return index


def _scenarios(total, bond_lots, curve, stock_value, foreign_stock_value):
    scenarios = [
        {"id": "stocks_-20", "label": "Las acciones caen 20%", "impact_mxn": round(-0.20 * stock_value, 2)},
        {"id": "mxn_+10", "label": "El peso se aprecia 10% (valen menos tus activos en moneda extranjera)",
         "impact_mxn": round(-0.10 * foreign_stock_value, 2)},
    ]
    if curve is not None:
        today = date.today()
        shock = 0.0
        for lot in bond_lots:
            shock += bond_math.market_value(lot, today, curve, shift=1.0) - bond_math.market_value(lot, today, curve)
        scenarios.append({"id": "rates_+1",
                          "label": "Las tasas de interés suben 1 punto (solo cuenta si vendes tus bonos antes de que venzan)",
                          "impact_mxn": round(shock, 2)})
    for s in scenarios:
        s["impact_percent"] = round(s["impact_mxn"] / total * 100, 2) if total else None
    return scenarios



def portfolio_risk_for(username, view=None):
    """Riesgo del portafolio de `username` (con `view` ya construida si se tiene).
    Lanza ValueError si el portafolio esta vacio."""
    view = view or build_portfolio_view(username)
    total = view["portfolio_total"]
    if not total:
        raise ValueError("El portafolio está vacío")

    stocks = [h for h in view["holdings"] if h["type"] == "accion" and h.get("value")]
    positions, stock_rows = {}, []
    for h in stocks:
        row = {"symbol": h["symbol"], "name": h["name"], "currency": h["currency"], "value": h["value"],
               "weight": round(h["value"] / total * 100, 2)}
        try:
            row.update({k: v for k, v in assess(h["symbol"]).items() if k in ("score", "level", "risky", "metrics")})
            positions[h["symbol"]] = load_stock(h["symbol"])
        except Exception as exc:
            row["error"] = _describe(exc)[0]
        stock_rows.append(row)

    scored = [r for r in stock_rows if r.get("score") is not None]
    stock_value = sum(h["value"] for h in stocks)
    weighted_score = (
        round(sum(r["score"] * r["value"] for r in scored) / sum(r["value"] for r in scored), 1) if scored else None
    )

    history = None
    if positions:
        weights = {s: next(h["value"] for h in stocks if h["symbol"] == s) / total for s in positions}
        try:
            index = _portfolio_index(positions, weights)
            prices = [p for _, p in index]
            # La escala de puntaje esta pensada para acciones sueltas; aplicada a una mezcla con
            # efectivo y bonos daria falsa tranquilidad. Se muestran los numeros junto a lo que hizo
            # el mercado global (ACWI, en pesos) en el mismo periodo, para tener contra que comparar.
            benchmark = [p for d, p in load_stock(BENCHMARK)["series_mxn"] if d >= index[0][0]]
            var, cvar = risk_engine.value_at_risk(prices)
            history = {
                "var": {"horizon_days": risk_engine.VAR_HORIZON, "confidence": round(risk_engine.VAR_CONFIDENCE * 100),
                        "var_percent": round(var * 100, 2), "cvar_percent": round(cvar * 100, 2),
                        "var_mxn": round(var * total, 2), "cvar_mxn": round(cvar * total, 2)},
                "volatility": round(risk_engine.annual_volatility(prices) * 100, 2),
                "tail_loss": round(risk_engine.tail_loss(prices) * 100, 2),
                "max_drawdown": round(risk_engine.max_drawdown(prices) * 100, 2),
                "benchmark": {
                    "symbol": BENCHMARK,
                    "volatility": round(risk_engine.annual_volatility(benchmark) * 100, 2),
                    "tail_loss": round(risk_engine.tail_loss(benchmark) * 100, 2),
                    "max_drawdown": round(risk_engine.max_drawdown(benchmark) * 100, 2),
                },
                "from": index[0][0], "to": index[-1][0],
                "covers_pct_of_portfolio": round(sum(weights.values()) * 100, 1),
            }
        except ValueError as exc:
            history = {"error": str(exc)}

    exposure = {}
    for h in view["holdings"]:
        if h.get("value"):
            currency = h["currency"] if h["type"] == "accion" else "MXN"
            exposure[currency] = exposure.get(currency, 0) + h["value"]
    exposure["MXN"] = exposure.get("MXN", 0) + view["cash"]
    foreign_stock_value = sum(h["value"] for h in stocks if h["currency"] != "MXN")

    holdings_json = pf_repo.get_portfolio(username)["holdings"]
    bond_lots = [h for h in holdings_json if h["type"] == "bono"]
    curve = None
    if bond_lots:
        try:
            curve = get_bond_curve()
        except Exception:
            pass

    top = max(view["holdings"], key=lambda h: h.get("value") or 0)
    return {
        "total": total,
        "currency": "MXN",
        "stocks": {"value": round(stock_value, 2), "share": round(stock_value / total * 100, 2),
                   "weighted_score": weighted_score,
                   "level": risk_engine.level_of(weighted_score) if weighted_score is not None else None,
                   "positions": sorted(stock_rows, key=lambda r: -r["value"])},
        "history": history,
        "concentration": {
            "largest_position": {"symbol": top["symbol"], "share": round((top.get("value") or 0) / total * 100, 2)},
            "currency_exposure": {c: round(v / total * 100, 2) for c, v in sorted(exposure.items(), key=lambda kv: -kv[1])},
            "cash_share": round(view["cash"] / total * 100, 2),
        },
        "scenarios": _scenarios(total, bond_lots, curve, stock_value, foreign_stock_value),
        "stress": _stress(stock_rows, total),
        "incomplete": view["incomplete"],
        "notes": [
            "Los bonos y el efectivo se tratan como estables en el historial; su riesgo de tasas aparece en los escenarios.",
            "El historial supone que siempre se tuvo la mezcla de hoy.",
            "El VaR es la pérdida que no se superó en el 95% de los meses de los últimos 3 años con la mezcla de hoy, dando más peso a los meses que se parecen "
            "a qué tan agitado está el mercado ahora; el CVaR es el promedio de los meses peores. Describe el pasado: no es una predicción ni un límite de pérdida.",
        ],
    }


@risk_bp.route("/portfolio", methods=["GET"])
@require_auth
@require_permission("risk")
def portfolio_risk():
    try:
        return jsonify(portfolio_risk_for(g.current_user["username"]))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422

