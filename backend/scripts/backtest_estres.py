"""Backtest del VaR estresado: ¿cubre un crash de mercado que NO estaba en los ultimos 3 anos?

Medida: perdida estresada = beta de la accion (o mezcla) x el peor mes del mercado global (ACWI, USD, ventanas de 21 dias
habiles) en TODA la historia disponible hasta la fecha de origen (desde marzo de 2008: incluye 2008, 2020 y 2022).
Es la perdida que tendria la cartera si el mercado repitiera su peor mes, segun su beta. Se compara contra el rendimiento
real de los 21 dias siguientes (ventanas sin traslape) y contra el VaR escalado de la app (risk_engine.value_at_risk).

Lo que dice el resultado:
  - excedencias: cuantas veces la perdida real fue peor que la estresada (deberia ser poco: es una medida de peor caso).
  - cobertura del crash 2020: el caso que el VaR de 3 anos no ve venir.
  - costo: cuanto mas grande es la perdida estresada que el VaR (si es 10 veces mas, no sirve como lectura).
Limites: la beta no ve el riesgo propio de cada empresa (una accion puede caer mas que el mercado por algo suyo); se ignora el
tipo de cambio (en una crisis el peso suele debilitarse, lo que amortigua la perdida en pesos de lo extranjero).

Uso (desde backend/):  python scripts/backtest_estres.py [--cache archivo.pkl] [--acwi acwi_diario.pkl]
"""
import bisect
import os
import pickle
import random
import sys
from datetime import date, datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backtest_risk  # noqa: E402
import backtest_var  # noqa: E402
from utils import risk_engine, yahoo_api  # noqa: E402

H, W = risk_engine.VAR_HORIZON, risk_engine.LONG_WINDOW


def acwi_daily(cache):
    """ACWI diario desde 2008 (con fechas explicitas Yahoo entrega diario; con range=max entrega mensual)."""
    if cache and os.path.exists(cache):
        return pickle.load(open(cache, "rb"))
    start = int(datetime(2008, 3, 1, tzinfo=timezone.utc).timestamp())
    end = int(datetime.now(timezone.utc).timestamp())
    response = yahoo_api._session().get(yahoo_api.CHART_URL.format(symbol="ACWI"), params={"period1": start, "period2": end, "interval": "1d"}, timeout=30)
    response.raise_for_status()
    series = yahoo_api._series_from_chart(response.json()["chart"]["result"][0])
    if cache:
        pickle.dump(series, open(cache, "wb"))
    return series


class Market:
    """Peor ventana de 21 dias del mercado hasta cada fecha (acumulado)."""

    def __init__(self, series):
        self.dates = [d for d, _ in series]
        prices = [p for _, p in series]
        self.weekly = risk_engine.weekly_returns(series)
        worst, self.running = 0.0, []
        for j in range(len(prices)):
            if j >= H:
                worst = min(worst, prices[j] / prices[j - H] - 1)
            self.running.append(worst)

    def worst_until(self, day):
        j = bisect.bisect_right(self.dates, day) - 1
        return self.running[j] if j >= 0 else 0.0


class Stock:
    def __init__(self, series):
        self.series = series
        self.weekly = risk_engine.weekly_returns(series)
        self.weeks = sorted(self.weekly)

    def beta_at(self, day, market):
        iso = date.fromisoformat(day).isocalendar()
        k = bisect.bisect_right(self.weeks, (iso[0], iso[1]))
        weeks = self.weeks[max(0, k - risk_engine.BETA_MAX_WEEKS - 4):k]
        return risk_engine.beta({w: self.weekly[w] for w in weeks}, market.weekly)


def stress_loss(beta, worst):
    return min(1.0, max(0.0, -(beta or 0.0) * worst))


def evaluate(dates, prices, beta_at, market):
    """[(origen, excedio, perdida estresada, VaR)] para una serie y su funcion de beta."""
    rows = []
    for i in range(W, len(prices) - H, H):
        beta = beta_at(dates[i])
        if beta is None:
            continue
        loss = stress_loss(beta, market.worst_until(dates[i]))
        var = risk_engine.value_at_risk(prices[i - W: i + 1])[0]
        real = prices[i + H] / prices[i] - 1
        rows.append((date.fromisoformat(dates[i]), real <= -loss, loss, var))
    return rows


def slices(rows):
    yield "todo el periodo", rows
    yield "origenes hasta 2019 (antes del covid)", [r for r in rows if r[0].year <= 2019]
    yield "origenes del crash 2020 (15-ene a 30-abr)", [r for r in rows if date(2020, 1, 15) <= r[0] <= date(2020, 4, 30)]
    yield "2021 en adelante", [r for r in rows if r[0].year >= 2021]


def line(title, rows):
    n = len(rows)
    if not n:
        return f"  {title:44} sin datos"
    x = sum(1 for r in rows if r[1])
    stress, var = mean(r[2] for r in rows), mean(r[3] for r in rows)
    return (f"  {title:44} n={n:5}  excedencias {x / n * 100:5.1f}%  perdida estresada prom {stress * 100:5.1f}%  "
            f"VaR prom {var * 100:5.1f}%  (estres/VaR {stress / var if var else float('nan'):4.1f}x)")


def main():
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    acwi_cache = sys.argv[sys.argv.index("--acwi") + 1] if "--acwi" in sys.argv else None
    data = backtest_risk.download(cache)
    market = Market(acwi_daily(acwi_cache))
    stocks = {s: Stock(v) for s, v in data.items() if s != backtest_risk.BENCHMARK and not isinstance(v, str)}

    singles = []
    for stock in stocks.values():
        singles += evaluate([d for d, _ in stock.series], [p for _, p in stock.series], lambda day, s=stock: s.beta_at(day, market), market)

    rng, mixes, names = random.Random(7), [], sorted(stocks)
    for _ in range(150):
        pick = [stocks[s] for s in rng.sample(names, 5)]
        dates, prices = backtest_var.portfolio_series([s.series for s in pick])
        if len(prices) <= W + H + 1:
            continue

        def mix_beta(day, pick=pick):
            betas = [s.beta_at(day, market) for s in pick]
            return None if None in betas else mean(betas)

        mixes += evaluate(dates, prices, mix_beta, market)

    worst = min(market.running)
    print(f"Peor mes del mercado global (ACWI, USD, 21 dias habiles) desde 2008: {worst * 100:.1f}%\n")
    for label, rows in (("ACCIONES SUELTAS", singles), ("CARTERAS DE 5 ACCIONES (150 al azar)", mixes)):
        print(f"== {label} ==")
        for title, subset in slices(rows):
            print(line(title, subset))
        print()


if __name__ == "__main__":
    main()
