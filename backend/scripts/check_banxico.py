"""Verifica contra Banxico REAL las series del catalogo de bonos (tabla instrumentos): que existan, que son lo
que el catalogo dice (CETES 28/91/182/364 y Bono M 10 anos) y que las tasas
recientes tengan sentido. Solo lee; no escribe nada.

Requiere BANXICO_TOKEN en backend/.env (se genera gratis en
https://www.banxico.org.mx/SieAPIRest/service/v1/token).

Que hay que revisar en la salida:
  - el titulo de cada serie debe mencionar el instrumento y el plazo correctos;
  - si dice "tasa de rendimiento" el calculo del proyecto es correcto; si dice
    "tasa de descuento" hay que convertirla (precio = nominal * (1 - d * dias/360)).

Uso (desde backend/):  python scripts/check_banxico.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

from config import Config  # noqa: E402
from utils import banxico_api  # noqa: E402
from utils.market_data import list_bonds  # noqa: E402

SANE_RATE_RANGE = (0.5, 25.0)  # % anual; fuera de esto casi seguro es otra serie


def fetch_titles(series_ids):
    url = f"{banxico_api.BASE_URL}/{','.join(series_ids)}"
    response = requests.get(url, headers=banxico_api._headers(), timeout=10)
    response.raise_for_status()
    return {s["idSerie"]: s.get("titulo", "(sin titulo)") for s in response.json()["bmx"]["series"]}


def main():
    if not Config.BANXICO_TOKEN:
        print("Falta BANXICO_TOKEN en backend/.env")
        return 1

    bonds = list_bonds()
    series_ids = [b["series_id"] for b in bonds]
    titles = fetch_titles(series_ids)
    rates = banxico_api.get_latest_rates(series_ids)

    problems = 0
    print(f"{'simbolo':10}{'serie':10}{'tasa %':>8}  titulo en Banxico")
    for bond in bonds:
        series = bond["series_id"]
        rate = rates.get(series)
        shown = "N/D" if rate is None else f"{rate:.2f}"
        print(f"{bond['symbol']:10}{series:10}{shown:>8}  {titles.get(series, '(la serie no existe)')}")
        if series not in titles or rate is None:
            problems += 1
        elif not SANE_RATE_RANGE[0] <= rate <= SANE_RATE_RANGE[1]:
            print(f"  ^ tasa fuera de rango razonable {SANE_RATE_RANGE}: probablemente no es una tasa de rendimiento")
            problems += 1

    cetes = sorted((b["term_days"], rates[b["series_id"]]) for b in bonds if b.get("kind") == "cetes" and b["series_id"] in rates)
    if any(later < earlier - 1.5 for (_, earlier), (_, later) in zip(cetes, cetes[1:])):
        print("Aviso: la curva de CETES baja mucho con el plazo; revisa que los 4 series sean los plazos correctos.")

    print("\nRevisa a mano los titulos: deben ser el instrumento y plazo del simbolo, y 'rendimiento' (no 'descuento').")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
