"""Backtest del puntaje de riesgo: ¿las acciones con puntaje alto de verdad tuvieron
una mala experiencia en los 12 meses siguientes?

Para cada accion y cada fecha de corte (trimestral) se calcula el puntaje usando
SOLO datos hasta esa fecha, y se compara con lo que paso despues:
  - caida maxima en los siguientes 252 dias habiles
  - rendimiento a 12 meses
"Mala experiencia" = caida maxima siguiente >= 30%.

Limites que conviene tener presentes al leer el resultado:
  - Se mide en la moneda de cada accion (no en pesos) para no bajar 10 anos de tipo de cambio.
  - Sesgo de supervivencia: el universo son empresas que siguen cotizando hoy; las que quebraron
    no estan, asi que los casos extremos se subestiman.
  - Las ventanas se traslapan y varias crisis (2020, 2022) pegaron a todas a la vez: son pocos
    "episodios" independientes aunque haya muchas filas.

Uso (desde backend/):  python scripts/backtest_risk.py [--cache archivo.pkl]
(con --cache las descargas se guardan y las siguientes corridas no vuelven a Yahoo)
"""
import os
import pickle
import sys
from collections import defaultdict
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import risk_engine, yahoo_api  # noqa: E402

BAD_DRAWDOWN = 0.30
BAD_RETURN = -0.15
FORWARD_DAYS = 252
BENCHMARK = "ACWI"

UNIVERSE = [
    # EE.UU. grandes
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "BAC", "XOM", "CVX", "KO", "PEP",
    "JNJ", "PFE", "WMT", "HD", "DIS", "NFLX", "INTC", "CSCO", "IBM", "GE", "F", "T", "VZ", "BA", "CAT",
    "MCD", "NKE",
    # mas volatiles / ciclicas
    "AMD", "MU", "CCL", "AAL", "UAL", "OXY", "FCX", "SLB", "C", "GM", "DAL", "MRNA",
    # internacionales
    "SAP.DE", "SIE.DE", "7203.T", "6758.T", "NESN.SW", "ASML.AS", "BP.L", "HSBA.L", "AZN.L", "0700.HK",
    "005930.KS", "AMXB.MX", "WALMEX.MX", "GFNORTEO.MX", "VALE", "BABA", "TSM",
]


def auc(scores, labels):
    """Probabilidad de que una accion 'mala' tenga mas puntaje que una 'buena' (0.5 = azar)."""
    pairs = sorted(zip(scores, labels))
    rank_sum, i, n = 0.0, 0, len(pairs)
    while i < n:
        j = i
        while j < n and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + 1 + j) / 2
        rank_sum += avg_rank * sum(1 for _, lab in pairs[i:j] if lab)
        i = j
    pos = sum(labels)
    neg = n - pos
    if pos == 0 or neg == 0:
        return None
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def quarter_origins(first_year, last):
    out = []
    for year in range(first_year, last.year + 1):
        for month in (1, 4, 7, 10):
            d = date(year, month, 1)
            if d <= last:
                out.append(d.isoformat())
    return out


def index_at(dates, origin):
    """Posicion del ultimo dato con fecha <= origin."""
    lo, hi = 0, len(dates) - 1
    if dates[0] > origin:
        return -1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if dates[mid] <= origin:
            lo = mid
        else:
            hi = mid - 1
    return lo


def download(cache_path):
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return pickle.load(f)
    print(f"Descargando {len(UNIVERSE) + 1} historicos de 10 anos...", flush=True)
    data = {BENCHMARK: yahoo_api.get_price_series(BENCHMARK, range_="10y")["series"]}
    for symbol in UNIVERSE:
        try:
            data[symbol] = yahoo_api.get_price_series(symbol, range_="10y")["series"]
        except Exception as exc:
            data[symbol] = str(exc)[:40]
    if cache_path:
        with open(cache_path, "wb") as f:
            pickle.dump(data, f)
    return data


def build_samples(cache_path=None):
    data = download(cache_path)
    bench = data[BENCHMARK]
    bench_dates = [d for d, _ in bench]
    origins = quarter_origins(2017, date.today())
    samples, skipped = [], []

    for symbol in UNIVERSE:
        series = data[symbol]
        if isinstance(series, str):
            skipped.append((symbol, series))
            continue
        dates = [d for d, _ in series]
        prices = [p for _, p in series]
        for origin in origins:
            i = index_at(dates, origin)
            if i < risk_engine.MIN_RETURNS or i + FORWARD_DAYS >= len(prices):
                continue
            j = index_at(bench_dates, origin)
            try:
                metrics = risk_engine.compute_metrics(series[: i + 1], series[: i + 1], bench[: j + 1])
            except ValueError:
                continue
            forward = prices[i: i + FORWARD_DAYS + 1]
            result = risk_engine.score_metrics(metrics)
            samples.append({
                "symbol": symbol, "origin": origin, "metrics": metrics, "score": result["score"],
                "level": result["level"], "fwd_drawdown": risk_engine.max_drawdown(forward),
                "fwd_return": forward[-1] / forward[0] - 1,
            })
    return samples, skipped


def bucket_report(samples, key="level"):
    rows = defaultdict(list)
    for s in samples:
        rows[s[key]].append(s)
    print(f"{'nivel':8}{'n':>6}{'caida max siguiente (prom)':>30}{'% con caida >= 30%':>22}{'rend. 12m (prom)':>20}{'% con rend. <= -15%':>22}")
    for level in ("bajo", "medio", "alto"):
        group = rows.get(level, [])
        if not group:
            print(f"{level:8}{0:>6}")
            continue
        n = len(group)
        print(f"{level:8}{n:>6}{sum(g['fwd_drawdown'] for g in group) / n * 100:>29.1f}%"
              f"{sum(g['fwd_drawdown'] >= BAD_DRAWDOWN for g in group) / n * 100:>21.1f}%"
              f"{sum(g['fwd_return'] for g in group) / n * 100:>19.1f}%"
              f"{sum(g['fwd_return'] <= BAD_RETURN for g in group) / n * 100:>21.1f}%")


def auc_report(samples, title):
    labels = [s["fwd_drawdown"] >= BAD_DRAWDOWN for s in samples]
    ret_labels = [s["fwd_return"] <= BAD_RETURN for s in samples]
    print(f"\n{title}  (n={len(samples)}, base de 'mala experiencia': caida>=30% {sum(labels) / len(labels) * 100:.1f}%, rend<=-15% {sum(ret_labels) / len(ret_labels) * 100:.1f}%)")
    print(f"  {'senal':38}{'AUC caida>=30%':>16}{'AUC rend<=-15%':>16}")
    total = [s["score"] for s in samples]
    print(f"  {'PUNTAJE TOTAL':38}{auc(total, labels):>16.3f}{auc(total, ret_labels):>16.3f}")
    for rule in risk_engine.RULES:
        pairs = [(s["metrics"][rule["id"]], l, r) for s, l, r in zip(samples, labels, ret_labels) if s["metrics"][rule["id"]] is not None]
        if len(pairs) < 50:
            continue
        a1 = auc([p[0] for p in pairs], [p[1] for p in pairs])
        a2 = auc([p[0] for p in pairs], [p[2] for p in pairs])
        print(f"  {rule['label']:38}{a1:>16.3f}{a2:>16.3f}")


WEIGHT_VARIANTS = {
    "actual (vol30 caida30 mes15 beta15 dist10)": {"volatility": 30, "max_drawdown": 30, "worst_month": 15, "beta": 15, "current_drawdown": 10},
    "sin distancia al maximo (beta25)": {"volatility": 30, "max_drawdown": 30, "worst_month": 15, "beta": 25},
    "beta 30, distancia 5": {"volatility": 25, "max_drawdown": 25, "worst_month": 15, "beta": 30, "current_drawdown": 5},
    "4 senales iguales (sin distancia)": {"volatility": 25, "max_drawdown": 25, "worst_month": 25, "beta": 25},
    "solo volatilidad y beta": {"volatility": 50, "beta": 50},
}


def composite(metrics, weights):
    num = den = 0.0
    for rule in risk_engine.RULES:
        weight, value = weights.get(rule["id"], 0), metrics.get(rule["id"])
        if weight and value is not None:
            num += weight * risk_engine.scale(value, rule["low"], rule["high"])
            den += weight
    return num / den


def variants_report(samples):
    print("\n== Variantes de pesos (AUC para caida>=30%; mas alto = mejor) ==")
    print(f"  {'variante':46}{'todo':>8}{'2017-20':>9}{'2021+':>8}{'sin crash 2020':>16}")
    groups = {
        "todo": samples,
        "early": [s for s in samples if s["origin"] < "2021-01-01"],
        "late": [s for s in samples if s["origin"] >= "2021-01-01"],
        "nocovid": [s for s in samples if not ("2019-07-01" <= s["origin"] <= "2020-04-01")],
    }
    for name, weights in WEIGHT_VARIANTS.items():
        cells = []
        for group in groups.values():
            cells.append(auc([composite(s["metrics"], weights) for s in group], [s["fwd_drawdown"] >= BAD_DRAWDOWN for s in group]))
        print(f"  {name:46}{cells[0]:>8.3f}{cells[1]:>9.3f}{cells[2]:>8.3f}{cells[3]:>16.3f}")


def main():
    cache_path = sys.argv[sys.argv.index("--cache") + 1] if "--cache" in sys.argv else None
    samples, skipped = build_samples(cache_path)
    if skipped:
        print("Sin datos:", skipped)
    print(f"\n{len(samples)} observaciones de {len({s['symbol'] for s in samples})} acciones, "
          f"cortes {min(s['origin'] for s in samples)} a {max(s['origin'] for s in samples)}\n")

    print("== Resultado por nivel de riesgo (umbrales actuales) ==")
    bucket_report(samples)

    auc_report(samples, "== Poder de discriminacion: todo el periodo ==")
    early = [s for s in samples if s["origin"] < "2021-01-01"]
    late = [s for s in samples if s["origin"] >= "2021-01-01"]
    auc_report(early, "== Cortes 2017-2020 ==")
    auc_report(late, "== Cortes 2021 en adelante ==")
    no_covid = [s for s in samples if not ("2019-07-01" <= s["origin"] <= "2020-04-01")]
    auc_report(no_covid, "== Sin cortes cuyo ano siguiente incluye el crash de 2020 ==")

    variants_report(samples)

    print("\n== Consistencia: ¿el puntaje alto de hoy sigue siendo alto? (corte siguiente) ==")
    by_symbol = defaultdict(list)
    for s in samples:
        by_symbol[s["symbol"]].append(s)
    same = total = 0
    for rows in by_symbol.values():
        rows.sort(key=lambda r: r["origin"])
        for a, b in zip(rows, rows[1:]):
            total += 1
            same += a["level"] == b["level"]
    print(f"  el nivel se mantiene de un trimestre al siguiente en {same / total * 100:.0f}% de los casos")


if __name__ == "__main__":
    main()

