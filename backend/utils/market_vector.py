"""Series del vector de precios de titulos gubernamentales 'on the run' del SIE de Banxico (estructura CF300).

Es el mercado secundario de cada dia: para cada titulo vigente publica su plazo por vencer, su precio limpio y sucio y su
rendimiento (CETES) o su cupon (bonos). De aqui sale la curva con la que se valuan los lotes antes de vencer.
Los codigos se tomaron del SIE y se validaron con la API el 8 de noviembre de 2026.
"""

# CETES: (plazo por vencer en dias, tasa de rendimiento)
CETES = [("SF45422", "SF45470"), ("SF45423", "SF45471"), ("SF45424", "SF45472"), ("SF45425", "SF45473"),
         ("SF349886", "SF349889")]

# Bonos M por rango de plazo: (plazo por vencer en dias, precio limpio, cupon vigente en %). El de 5 a 7 anios hoy no cotiza (N/E).
BONOS_M = [("SF45427", "SF45448", "SF45475"),  # 0 a 3 anios
           ("SF45428", "SF45450", "SF45476"),  # 3 a 5
           ("SF45429", "SF45452", "SF45477"),  # 5 a 7
           ("SF45430", "SF45454", "SF45478"),  # 7 a 10
           ("SF45431", "SF45456", "SF45479"),  # 10 a 20
           ("SF60720", "SF60721", "SF60723")]  # 20 a 30


def all_series():
    ids = [s for pair in CETES for s in pair]
    ids += [s for triple in BONOS_M for s in triple]
    return ids
