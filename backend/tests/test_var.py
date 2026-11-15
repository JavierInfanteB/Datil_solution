"""VaR y CVaR historicos (risk_engine.value_at_risk): casos con respuesta conocida y propiedades que siempre deben cumplirse."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import risk_engine  # noqa: E402


def creciendo(diario, n=800):
    """Precios que cambian lo mismo todos los dias."""
    return [100 * (1 + diario) ** i for i in range(n)]


def azar(vol, n=800, semilla=3):
    rng, precio, out = random.Random(semilla), 100.0, [100.0]
    for _ in range(n):
        precio *= 1 + rng.gauss(0.0003, vol)
        out.append(precio)
    return out


class ValueAtRiskTest(unittest.TestCase):
    def test_sin_meses_malos_no_hay_perdida(self):
        self.assertEqual(risk_engine.value_at_risk(creciendo(0.0005)), (0.0, 0.0))

    def test_si_todos_los_meses_caen_igual_el_var_es_esa_caida(self):
        esperado = 1 - 0.998 ** risk_engine.VAR_HORIZON
        var, cvar = risk_engine.value_at_risk(creciendo(-0.002))
        self.assertAlmostEqual(var, esperado, places=9)
        self.assertAlmostEqual(cvar, esperado, places=9)

    def test_el_cvar_nunca_es_menor_que_el_var(self):
        for vol in (0.005, 0.01, 0.02, 0.04):
            var, cvar = risk_engine.value_at_risk(azar(vol))
            self.assertGreaterEqual(cvar, var)

    def test_mas_volatil_da_mas_var(self):
        calma, brava = (risk_engine.value_at_risk(azar(v))[0] for v in (0.006, 0.025))
        self.assertGreater(brava, calma * 2)

    def test_mas_confianza_da_mas_var(self):
        precios = azar(0.015)
        self.assertGreaterEqual(risk_engine.value_at_risk(precios, confidence=0.99)[0], risk_engine.value_at_risk(precios, confidence=0.95)[0])

    def test_solo_cuenta_los_ultimos_tres_anos(self):
        crash_viejo = [100.0] * 50 + [10.0] * 50  # una caida de 90% anterior a la ventana
        precios = crash_viejo + [10 * 1.0005 ** i for i in range(risk_engine.LONG_WINDOW + 1)]
        self.assertEqual(risk_engine.value_at_risk(precios), (0.0, 0.0))

    def test_con_poca_historia_avisa_en_vez_de_inventar(self):
        with self.assertRaises(ValueError):
            risk_engine.value_at_risk(azar(0.01, n=80))


if __name__ == "__main__":
    unittest.main()
