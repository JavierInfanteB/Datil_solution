"""Experimento: ¿un VaR que se ajusta a la volatilidad del momento subestima menos en un crash?

Compara, con el mismo backtest de excedencias de backtest_var.py (VaR a 21 dias habiles, 95%, ventana de 3 anos, ventanas de
evaluacion sin traslape, acciones sueltas y carteras de 5 al azar), estas variantes:

  historico     el VaR de risk_engine.value_at_risk (cada mes del pasado pesa igual)
  hw94 / hw97   Hull-White: cada ventana del pasado se multiplica por vol_hoy / vol_al_inicio_de_esa_ventana, con la volatilidad
                EWMA (lambda 0.94 o 0.97). Si hoy el mercado esta mas agitado que entonces, esa ventana cuenta como mas grande.
  hw94 acotado  igual, con el factor limitado a [0.5, 2] para que una calma extrema no dispare las ventanas.
  max(hist,hw94) el mayor de los dos: nunca baja del historico y sube cuando la volatilidad de hoy esta alta.

Ademas de las excedencias se imprime el VaR promedio (que tan conservador es) y los origenes de 2020-01-15 a 2020-04-30 y de 2022.

Uso (desde backend/):  python scripts/backtest_var_filtrado.py [--cache archivo.pkl]
"""
import math
import os
import random
import sys
from datetime import date
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import backtest_risk  # noqa: E402
import backtest_var  # noqa: E402
from utils import risk_engine  # noqa: E402

H, W = risk_engine.VAR_HORIZON, risk_engine.LONG_WINDOW
CUT = 1 - risk_engine.VAR_CONFIDENCE


def ewma_vol(prices, lam):
    """Volatilidad diaria EWMA tras ver cada precio (indice k: usa los rendimientos hasta prices[k])."""
    returns = [prices[k] / prices[k - 1] - 1 for k in range(1, len(prices))]
    var = mean(r * r for r in returns[:30])
    out = [None]
    for r in returns:
        var = lam * var + (1 - lam) * r * r
        out.append(math.sqrt(var))
    return out


def tail_var(windows):
    windows = sorted(windows)
    tail = windows[: max(1, int(len(windows) * CUT))]
    return max(0.0, -tail[-1]), max(0.0, -mean(tail))


def hull_white(prices, vols, i, lo=None, hi=None):
    """VaR/CVaR con las ventanas de prices[i-W..i] reescaladas por vol_hoy / vol_inicio."""
    out = []
    for j in range(i - W, i - H + 1):
        factor = vols[i] / vols[j] if vols[j] else 1.0
        if lo is not None:
            factor = min(hi, max(lo, factor))
        out.append((prices[j + H] / prices[j] - 1) * factor)
    return tail_var(out)


VARIANTS = ["historico", "hw94", "hw94 acotado", "hw97", "max(hist,hw94)"]


def evaluate(dates, prices):
    """{variante: [(origen, excedio, perdida real, VaR, CVaR)]} con ventanas de evaluacion sin traslape."""
    v94, v97 = ewma_vol(prices, 0.94), ewma_vol(prices, 0.97)
    out = {name: [] for name in VARIANTS}
    for i in range(W, len(prices) - H, H):
        real = prices[i + H] / prices[i] - 1
        origin = date.fromisoformat(dates[i])
        hist = risk_engine.value_at_risk(prices[i - W: i + 1])
        hw94 = hull_white(prices, v94, i)
        results = {"historico": hist, "hw94": hw94, "hw94 acotado": hull_white(prices, v94, i, 0.5, 2.0),
                   "hw97": hull_white(prices, v97, i), "max(hist,hw94)": (max(hist[0], hw94[0]), max(hist[1], hw94[1]))}
        for name, (var, cvar) in results.items():
            out[name].append((origin, real <= -var, max(0.0, -real), var, cvar))
    return out


def merge(parts):
    return {name: [r for part in parts for r in part[name]] for name in VARIANTS}


def slices(rows):
    yield "todo el periodo", rows
    yield "2021 en adelante", [r for r in rows if r[0].year >= 2021]
    yield "orígenes del crash 2020 (15-ene a 30-abr)", [r for r in rows if date(2020, 1, 15) <= r[0] <= date(2020, 4, 30)]
    yield "orígenes de 2022", [r for r in rows if r[0].year == 2022]
    yield "sin el crash de 2020", [r for r in rows if not backtest_var.CRASH_2020[0] <= r[0] <= backtest_var.CRASH_2020[1]]


def line(title, rows):
    n = len(rows)
    if not n:
        return f"    {title:44} sin datos"
    x = sum(1 for r in rows if r[1])
    return f"    {title:44} n={n:5}  excedencias {x / n * 100:5.1f}%  VaR promedio {mean(r[3] for r in rows) * 100:5.1f}%"


def main():
    cache = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    data = backtest_risk.download(cache)
    stocks = {s: v for s, v in data.items() if s != backtest_risk.BENCHMARK and not isinstance(v, str)}

    singles = merge([evaluate([d for d, _ in s], [p for _, p in s]) for s in stocks.values()])
    rng, parts, names = random.Random(7), [], sorted(stocks)
    for _ in range(150):
        dates, prices = backtest_var.portfolio_series([stocks[s] for s in rng.sample(names, 5)])
        if len(prices) > W + H + 1:
            parts.append(evaluate(dates, prices))
    mixes = merge(parts)

    print(f"{len(stocks)} acciones; VaR a {H} dias habiles, 95%, ventana de {W} dias; esperado: 5% de excedencias\n")
    for label, result in (("ACCIONES SUELTAS", singles), ("CARTERAS DE 5 ACCIONES (150 al azar)", mixes)):
        print(f"== {label} ==")
        for title, _ in slices(result["historico"]):
            print(f"  [{title}]")
            for name in VARIANTS:
                subset = dict(slices(result[name]))[title]
                print(f"    {name:16}" + line("", subset).strip()[len(""):])
        print()


if __name__ == "__main__":
    main()
