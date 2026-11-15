"""Backtest del VaR historico a un mes (95%): ¿con que frecuencia la perdida real del mes siguiente supero al VaR?
Si el VaR esta bien calibrado, debe pasar cerca del 5% de las veces.

Para cada accion y para carteras al azar de 5 acciones (igual peso, mezcla constante, como el indice que arma la app),
cada 21 dias habiles se calcula el VaR con los 3 anos previos (risk_engine.value_at_risk) y se compara contra el
rendimiento de los 21 dias siguientes. Las ventanas de evaluacion NO se traslapan. Prueba de Kupiec (POF) sobre la tasa
de excedencias y comparacion del CVaR predicho contra la perdida real promedio cuando hubo excedencia.

Limites a tener presentes al leer el resultado:
  - Se mide en la moneda de cada accion (no en pesos), igual que backtest_risk.py.
  - Las acciones y las carteras comparten crisis (2020, 2022): las excedencias no son independientes entre si, asi que
    el valor p de Kupiec es optimista. Mas que el valor p, mirar la tasa por periodo.
  - Sesgo de supervivencia: el universo son empresas que siguen cotizando hoy.

Uso (desde backend/):  python scripts/backtest_var.py [--cache archivo.pkl]
(reusa el cache de backtest_risk.py: las descargas se guardan y las siguientes corridas no vuelven a Yahoo)
"""
import math
import os
import random
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backtest_risk  # noqa: E402
from utils import risk_engine  # noqa: E402

H, W = risk_engine.VAR_HORIZON, risk_engine.LONG_WINDOW
EXPECTED = 1 - risk_engine.VAR_CONFIDENCE
CRASH_2020 = (date(2020, 1, 15), date(2020, 4, 30))  # origenes cuyo mes siguiente cae en el crash del covid


def evaluate(dates, prices):
    """[(fecha de origen, excedio, perdida real, VaR, CVaR)] con ventanas de H dias sin traslape."""
    rows = []
    for i in range(W, len(prices) - H, H):
        var, cvar = risk_engine.value_at_risk(prices[i - W: i + 1])
        real = prices[i + H] / prices[i] - 1
        rows.append((date.fromisoformat(dates[i]), real <= -var, max(0.0, -real), var, cvar))
    return rows


def portfolio_series(series_list):
    """Indice de una mezcla de igual peso con rebalanceo diario sobre las fechas comunes."""
    by_day = [dict(s) for s in series_list]
    days = sorted(set.intersection(*(set(d) for d in by_day)))
    level, out = 100.0, [(days[0], 100.0)]
    for a, b in zip(days, days[1:]):
        level *= 1 + sum(d[b] / d[a] - 1 for d in by_day) / len(by_day)
        out.append((b, level))
    return [d for d, _ in out], [p for _, p in out]


def kupiec(n, x, p=EXPECTED):
    """Valor p de la prueba de proporcion de fallas de Kupiec (chi cuadrada, 1 gl)."""
    if n == 0:
        return None
    pi = x / n
    if x in (0, n):
        ll_alt = 0.0
    else:
        ll_alt = (n - x) * math.log(1 - pi) + x * math.log(pi)
    lr = -2 * ((n - x) * math.log(1 - p) + x * math.log(p) - ll_alt)
    return math.erfc(math.sqrt(max(lr, 0.0) / 2))


def report(title, rows):
    n = len(rows)
    if n == 0:
        print(f"  {title:42}  sin datos")
        return
    x = sum(1 for r in rows if r[1])
    hits = [r for r in rows if r[1]]
    ratio = (sum(r[2] for r in hits) / sum(r[4] for r in hits)) if hits else float("nan")
    print(f"  {title:42} n={n:5}  excedencias={x / n * 100:5.1f}% (esperado {EXPECTED * 100:.0f}%)  Kupiec p={kupiec(n, x):.3f}  "
          f"perdida real / CVaR predicho en excedencias={ratio:4.2f}")


def slices(rows):
    yield "todo el periodo", rows
    yield "origenes hasta 2020", [r for r in rows if r[0].year <= 2020]
    yield "origenes 2021 en adelante", [r for r in rows if r[0].year >= 2021]
    yield "sin el crash de 2020", [r for r in rows if not CRASH_2020[0] <= r[0] <= CRASH_2020[1]]


def main():
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    data = backtest_risk.download(cache)
    stocks = {s: v for s, v in data.items() if s != backtest_risk.BENCHMARK and not isinstance(v, str)}

    singles = []
    for series in stocks.values():
        singles += evaluate([d for d, _ in series], [p for _, p in series])

    rng, mixes = random.Random(7), []
    names = sorted(stocks)
    for _ in range(150):
        dates, prices = portfolio_series([stocks[s] for s in rng.sample(names, 5)])
        if len(prices) > W + H + 1:
            mixes += evaluate(dates, prices)

    print(f"{len(stocks)} acciones; VaR a {H} dias habiles, confianza {risk_engine.VAR_CONFIDENCE * 100:.0f}%, ventana de {W} dias\n")
    for label, rows in (("ACCIONES SUELTAS", singles), ("CARTERAS DE 5 ACCIONES (150 al azar)", mixes)):
        print(f"== {label} ==")
        for title, subset in slices(rows):
            report(title, subset)
        print()


if __name__ == "__main__":
    main()
