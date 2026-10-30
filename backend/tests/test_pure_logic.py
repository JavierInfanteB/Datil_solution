"""Riesgo, contexto de operaciones y sugerencias: logica pura, sin red ni archivos.

Se corre desde backend/:  python -m unittest discover -s tests
"""
import math
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import advice, risk_engine, trade_timing  # noqa: E402


def series(prices, start=date(2024, 1, 1)):
    return [((start + timedelta(days=n)).isoformat(), p) for n, p in enumerate(prices)]


# Sube 0.05% diario 300 dias y luego cae 0.5% diario 100 dias.
PRICES = [100 * 1.0005 ** n for n in range(300)] + [100 * 1.0005 ** 299 * 0.995 ** n for n in range(1, 101)]


class RiskEngineTest(unittest.TestCase):
    def test_tail_loss_promedia_los_peores_dias(self):
        prices = [100.0] * 300
        prices[150] = 90.0  # un solo dia de -10% y regresa: 299 rendimientos, el 5% peor son 14 dias
        self.assertAlmostEqual(risk_engine.tail_loss(prices), -math.log(0.9) / 14)
        self.assertEqual(risk_engine.tail_loss([100.0 * 1.001 ** n for n in range(300)]), 0.0)

    def test_los_cortes_de_nivel(self):
        self.assertEqual(risk_engine.level_of(risk_engine.MEDIUM_FROM - 0.1), "bajo")
        self.assertEqual(risk_engine.level_of(risk_engine.MEDIUM_FROM), "medio")
        self.assertEqual(risk_engine.level_of(risk_engine.HIGH_FROM), "alto")

    def test_mas_riesgo_en_las_senales_da_mas_puntaje(self):
        calm = {"volatility": 18, "tail_loss": 2.2, "max_drawdown": 15, "beta": 0.7}
        wild = {"volatility": 55, "tail_loss": 7.0, "max_drawdown": 55, "beta": 1.7}
        self.assertLess(risk_engine.score_metrics(calm)["score"], risk_engine.MEDIUM_FROM)
        self.assertGreaterEqual(risk_engine.score_metrics(wild)["score"], risk_engine.HIGH_FROM)

    def test_no_hay_metricas_de_rendimiento(self):
        metrics = risk_engine.compute_metrics(series(PRICES))
        self.assertNotIn("return_1y", metrics)
        self.assertEqual(sum(r["weight"] for r in risk_engine.RULES), 100)


class TradeTimingTest(unittest.TestCase):
    def setUp(self):
        self.prices = series(PRICES)
        self.bench = series([100 * 1.0003 ** n * (1 + 0.01 * math.sin(n)) for n in range(len(PRICES))])

    def analyze(self, index, side):
        return trade_timing.analyze(self.prices, self.prices, self.bench, self.prices[index][0], side)

    def test_compra_en_el_maximo(self):
        timing = self.analyze(299, "buy")
        self.assertEqual(timing["from_peak_pct"], 0.0)
        self.assertLess(timing["after"]["worst_pct"], -35)
        self.assertIn("Compra cerca de su máximo de 52 semanas", timing["flags"])
        self.assertIsNotNone(timing["risk"])

    def test_venta_tras_una_caida(self):
        timing = self.analyze(399, "sell")
        self.assertGreaterEqual(timing["from_peak_pct"], trade_timing.FALLING)
        self.assertIn("Venta tras una caída fuerte", timing["flags"])

    def test_con_poca_historia_no_hay_puntaje_pero_si_contexto(self):
        timing = self.analyze(100, "buy")
        self.assertIsNone(timing["risk"])
        self.assertEqual(timing["after"]["now_pct"], round((PRICES[-1] / PRICES[100] - 1) * 100, 1))

    def test_fecha_anterior_a_la_historia(self):
        self.assertIsNone(trade_timing.analyze(self.prices, self.prices, self.bench, "2000-01-01", "buy"))

    def test_dias_que_se_tuvo_lo_vendido(self):
        def tx(id, day, side, quantity):
            return {"id": id, "date": f"2025-01-{day:02d}T10:00:00+00:00", "type": "accion", "symbol": "X",
                    "side": side, "quantity": quantity}

        transactions = [tx("b1", 1, "buy", 10), tx("b2", 11, "buy", 10), tx("s1", 21, "sell", 15),
                        tx("s2", 25, "sell", 100)]
        held = trade_timing.holding_days(transactions)
        self.assertEqual(held["s1"], round((10 * 20 + 5 * 10) / 15))
        self.assertEqual(held["s2"], 14)  # solo quedaban 5 con compra registrada, de 14 dias
        self.assertEqual(trade_timing.holding_days([tx("s", 5, "sell", 1)]), {})


def risk_of(positions, **overrides):
    risk = {
        "total": 100_000.0, "incomplete": False, "history": None, "scenarios": [],
        "stocks": {"share": 80.0, "positions": positions},
        "concentration": {"cash_share": 20.0, "currency_exposure": {"MXN": 20.0, "USD": 80.0}},
    }
    return {**risk, **overrides}


def position(symbol, weight, level="bajo", score=20.0):
    return {"symbol": symbol, "weight": weight, "level": level, "score": score}


class AdviceTest(unittest.TestCase):
    def ids(self, risk):
        return [s["id"] for s in advice.suggestions(risk)]

    def test_concentracion_calcula_cuanto_vender(self):
        found = advice.suggestions(risk_of([position("AAPL", 60), position("MSFT", 20)]))
        first = found[0]
        self.assertEqual((first["id"], first["severity"], first["symbol"]), ("concentration", "alta", "AAPL"))
        self.assertEqual(first["amount_mxn"], 35_000.0)  # de 60% a 25% de 100,000

    def test_accion_de_riesgo_alto_con_peso(self):
        self.assertIn("risky_stock", self.ids(risk_of([position("TSLA", 12, "alto", 70)] + [position("A", 10)] * 2)))
        self.assertNotIn("risky_stock", self.ids(risk_of([position("TSLA", 5, "alto", 70)] + [position("A", 10)] * 2)))

    def test_portafolio_sano_no_genera_sugerencias(self):
        sano = risk_of([position("A", 20), position("B", 20), position("C", 20), position("D", 20)],
                       concentration={"cash_share": 20.0, "currency_exposure": {"MXN": 60.0, "USD": 40.0}})
        self.assertEqual(advice.suggestions(sano), [])

    def test_escenario_malo_y_orden_por_gravedad(self):
        scenarios = [{"id": "s", "label": "Las acciones caen 20%", "impact_mxn": -30000.0, "impact_percent": -30.0}]
        balanced = {"cash_share": 20.0, "currency_exposure": {"MXN": 60.0, "USD": 40.0}}
        found = advice.suggestions(
            risk_of([position("A", 20)] * 3, scenarios=scenarios, incomplete=True, concentration=balanced))
        self.assertEqual([s["id"] for s in found], ["scenario", "incomplete"])
        self.assertEqual(found[0]["severity"], "alta")
        self.assertIn("-$30,000", found[0]["detail"])

    def test_nunca_sugiere_comprar(self):
        text = " ".join(s["title"] + s["detail"] for s in advice.suggestions(risk_of([position("AAPL", 60)])))
        self.assertNotIn("compr", text.lower())


if __name__ == "__main__":
    unittest.main()
