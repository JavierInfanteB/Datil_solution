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
    return por_tramos([(vol, n)], semilla)


def por_tramos(tramos, semilla=5):
    """Precios al azar con la volatilidad diaria de cada tramo: [(vol, dias), ...]."""
    rng, precio, out = random.Random(semilla), 100.0, [100.0]
    for vol, dias in tramos:
        for _ in range(dias):
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

    def test_si_el_mercado_se_agita_el_var_sube(self):
        precios = por_tramos([(0.006, 700), (0.03, 60)])
        self.assertGreater(risk_engine.value_at_risk(precios)[0], 2 * risk_engine.value_at_risk(precios, vol_scaled=False)[0])

    def test_si_el_mercado_se_calma_el_var_baja(self):
        precios = por_tramos([(0.03, 60), (0.006, 700)])
        self.assertLess(risk_engine.value_at_risk(precios)[0], risk_engine.value_at_risk(precios, vol_scaled=False)[0])

    def test_con_volatilidad_constante_escalar_casi_no_cambia_nada(self):
        precios = azar(0.012)
        escalado, plano = (risk_engine.value_at_risk(precios, vol_scaled=s)[0] for s in (True, False))
        self.assertAlmostEqual(escalado, plano, delta=0.35 * plano)

    def test_ewma_sigue_la_volatilidad_reciente(self):
        vols = risk_engine.ewma_vol(por_tramos([(0.005, 300), (0.03, 100)]))
        self.assertIsNone(vols[0])
        self.assertGreater(vols[-1], 3 * vols[250])

    def test_con_poca_historia_avisa_en_vez_de_inventar(self):
        with self.assertRaises(ValueError):
            risk_engine.value_at_risk(azar(0.01, n=80))


if __name__ == "__main__":
    unittest.main()
