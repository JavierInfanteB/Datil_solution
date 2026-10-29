"""Reglas de negocio para medir el riesgo de una accion (sin I/O).

Pregunta que responde: "si compro esto y lo mantengo un ano, ¿que tan
probable es que sea una mala experiencia?". Se mide con cinco senales
historicas, cada una llevada a una escala 0-100 entre un umbral "bajo" y uno
"alto", y el puntaje final es el promedio ponderado:

    volatilidad (1 ano)  25   cuanto se mueve el precio dia a dia
    caida maxima (3 a.)  25   la peor caida pico-a-valle que ya vivio
    peor mes (3 a.)      15   el peor mes que ya vivio
    beta                 30   cuanto amplifica los movimientos del mercado global
    distancia al maximo   5   si hoy viene cayendo (52 semanas)

Los pesos y umbrales (RULES) se calibraron con scripts/backtest_risk.py, que
compara el puntaje contra lo que realmente paso los 12 meses siguientes: la
beta fue la senal que mejor distinguio y la distancia al maximo la mas debil,
por eso se movieron pesos de una a otra. Con 60 acciones y solo un par de
crisis en la muestra, el ajuste es deliberadamente moderado; si se vuelve a
calibrar, hay que correr el backtest otra vez y comparar.
Volatilidad, caidas y peor mes se miden en PESOS, porque es el
dinero del usuario: una accion extranjera tambien lleva el riesgo cambiario.
La beta usa los precios en su moneda original contra un ETF global, con
rendimientos semanales para que los distintos horarios de bolsa no la sesguen.
"""
import math
from datetime import date
from statistics import mean, stdev

TRADING_DAYS = 252
YEAR_WINDOW = TRADING_DAYS
LONG_WINDOW = 3 * TRADING_DAYS
MONTH_DAYS = 21
MIN_RETURNS = 250  # menos de ~1 ano de historia no alcanza para medir riesgo
BETA_MAX_WEEKS = 156
BETA_MIN_WEEKS = 52

# weight: peso en el puntaje. low/high: valor que da 0 y valor que da 100.
RULES = [
    {"id": "volatility", "label": "Volatilidad anual (1 ano)", "weight": 25, "low": 15, "high": 60, "unit": "%"},
    {"id": "max_drawdown", "label": "Caida maxima (3 anos)", "weight": 25, "low": 10, "high": 60, "unit": "%"},
    {"id": "worst_month", "label": "Peor mes (3 anos)", "weight": 15, "low": 5, "high": 35, "unit": "%"},
    {"id": "beta", "label": "Beta vs mercado global", "weight": 30, "low": 0.6, "high": 1.8, "unit": ""},
    {"id": "current_drawdown", "label": "Distancia al maximo de 52 semanas", "weight": 5, "low": 0, "high": 40, "unit": "%"},
]
MEDIUM_FROM = 35  # puntaje < 35 = bajo
HIGH_FROM = 60  # puntaje >= 60 = alto; "riesgosa" = alto


def level_of(score):
    if score < MEDIUM_FROM:
        return "bajo"
    return "medio" if score < HIGH_FROM else "alto"


def scale(value, low, high):
    return max(0.0, min(100.0, (value - low) / (high - low) * 100))


def log_returns(prices):
    return [math.log(b / a) for a, b in zip(prices, prices[1:])]


def max_drawdown(prices):
    """Peor caida pico-a-valle como fraccion positiva (0.35 = -35%)."""
    peak, worst = prices[0], 0.0
    for price in prices:
        peak = max(peak, price)
        worst = min(worst, price / peak - 1)
    return -worst


def annual_volatility(prices):
    returns = log_returns(prices)[-YEAR_WINDOW:]
    return stdev(returns) * math.sqrt(TRADING_DAYS)


def worst_month(prices):
    """Peor rendimiento en ventanas de ~un mes, como fraccion positiva."""
    losses = [1 - prices[i] / prices[i - MONTH_DAYS] for i in range(MONTH_DAYS, len(prices))]
    return max(0.0, max(losses)) if losses else 0.0


def weekly_returns(series):
    """{(ano, semana ISO): rendimiento} usando el ultimo precio de cada semana."""
    last_by_week = {}
    for day, price in series:  # la serie viene ordenada: el ultimo dia de la semana gana
        iso = date.fromisoformat(day).isocalendar()
        last_by_week[(iso[0], iso[1])] = price
    weeks = sorted(last_by_week)
    return {cur: last_by_week[cur] / last_by_week[prev] - 1 for prev, cur in zip(weeks, weeks[1:])}


def beta(stock_weekly, bench_weekly):
    weeks = sorted(set(stock_weekly) & set(bench_weekly))[-BETA_MAX_WEEKS:]
    if len(weeks) < BETA_MIN_WEEKS:
        return None
    xs = [bench_weekly[w] for w in weeks]
    ys = [stock_weekly[w] for w in weeks]
    mx, my = mean(xs), mean(ys)
    variance = sum((x - mx) ** 2 for x in xs)
    if variance == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / variance


def compute_metrics(series_mxn, series_native=None, bench_native=None):
    """Metricas de riesgo. `series_mxn` es la serie en pesos; `series_native`
    y `bench_native` (moneda original y ETF global) solo se usan para la beta.
    Porcentajes en puntos (35.0 = 35%)."""
    prices = [p for _, p in series_mxn]
    if len(prices) - 1 < MIN_RETURNS:
        raise ValueError(
            f"Historia insuficiente: {len(prices) - 1} dias de rendimientos, se necesitan al menos {MIN_RETURNS}"
        )

    long_prices = prices[-LONG_WINDOW - 1:]
    metrics = {
        "volatility": annual_volatility(prices) * 100,
        "max_drawdown": max_drawdown(long_prices) * 100,
        "worst_month": worst_month(long_prices) * 100,
        "current_drawdown": (1 - prices[-1] / max(prices[-YEAR_WINDOW:])) * 100,
        "beta": None,
        "return_1y": (prices[-1] / prices[-YEAR_WINDOW - 1] - 1) * 100 if len(prices) > YEAR_WINDOW else None,
        "volatility_native": None,
    }
    if series_native and len(series_native) - 1 >= MIN_RETURNS:
        metrics["volatility_native"] = annual_volatility([p for _, p in series_native]) * 100
    if series_native and bench_native:
        metrics["beta"] = beta(weekly_returns(series_native), weekly_returns(bench_native))
    return metrics


def score_metrics(metrics):
    """Puntaje 0-100 con el desglose por senal. Si falta una senal (p. ej. la
    beta por historia corta) se excluye y los pesos restantes se reescalan."""
    factors, weighted, total_weight = [], 0.0, 0
    for rule in RULES:
        value = metrics.get(rule["id"])
        span = rule["high"] - rule["low"]
        factor = {"id": rule["id"], "label": rule["label"], "weight": rule["weight"], "unit": rule["unit"],
                  # Valor de la senal en el que pasa a "medio" y a "alto" (no los extremos de la escala 0-100).
                  "medium_from": round(rule["low"] + span * MEDIUM_FROM / 100, 2),
                  "high_from": round(rule["low"] + span * HIGH_FROM / 100, 2),
                  "value": None if value is None else round(value, 2)}
        if value is None:
            factor.update(score=None, level=None, available=False)
        else:
            s = scale(value, rule["low"], rule["high"])
            factor.update(score=round(s, 1), level=level_of(s), available=True)
            weighted += rule["weight"] * s
            total_weight += rule["weight"]
        factors.append(factor)

    score = weighted / total_weight if total_weight else None
    return {
        "score": None if score is None else round(score, 1),
        "level": None if score is None else level_of(score),
        "risky": score is not None and score >= HIGH_FROM,
        "factors": factors,
        "missing": [f["label"] for f in factors if not f["available"]],
    }


def normalize(series, start_index=0):
    """Serie base 100 desde `start_index`, para comparar acciones."""
    base = series[start_index][1]
    return [(day, price / base * 100) for day, price in series[start_index:]]
