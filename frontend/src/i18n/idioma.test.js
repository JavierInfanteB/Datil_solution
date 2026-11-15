import { test } from "node:test";
import assert from "node:assert/strict";
import { traducir } from "./idioma.js";
import { EXACTO, PLANTILLAS } from "./en.js";

test("traduce textos fijos y conserva el resto", () => {
  assert.equal(traducir("Cerrar sesión"), "Log out");
  assert.equal(traducir("  Cerrar   sesión "), "Log out");  // espacios colapsados
  assert.equal(traducir("Algo que no está en el diccionario"), null);
});

test("las frases con cifras se traducen con cualquier número y nombre", () => {
  assert.equal(traducir("Reducir AAPL: pesa 40.74% del portafolio"), "Reduce AAPL: it weighs 40.74% of the portfolio");
  assert.equal(traducir("TSLA tiene riesgo alto y pesa 16.15%"), "TSLA has high risk and weighs 16.15%");
  assert.equal(traducir("Las acciones caen 20%: -$127,668."), "Stocks fall 20%: -$127,668.");
  assert.equal(traducir("Compra de 3 × TSLA"), "Purchase of 3 × TSLA");
  assert.equal(
    traducir("Llevarla a 25% implica vender unos $112,076. Si las acciones cayeran 20%, se perderían unos $22,415 menos."),
    "Bringing it to 25% means selling about $112,076. If stocks fell 20%, about $22,415 less would be lost.",
  );
});

test("ninguna entrada del diccionario queda vacía y las plantillas usan todas sus capturas", () => {
  for (const [es, en] of Object.entries(EXACTO)) assert.ok(en.trim() !== "" && es.trim() !== "", es);
  for (const [es, en] of PLANTILLAS) {
    const capturas = (es.match(/\{n\}|\{\*\}/g) ?? []).length;
    for (let i = 1; i <= capturas; i++) assert.ok(en.includes(`{${i}}`), `${es} no usa {${i}}`);
  }
});

test("el VaR, el estrés y el nivel del cliente tienen traducción", () => {
  for (const es of [
    "Pérdida en un mal mes (VaR)", "Pérdida en los peores meses (CVaR)", "Si el mercado repitiera su peor mes", "Pérdida estresada",
    "Peor mes del mercado global", "Beta del portafolio", "Nivel de riesgo de tu portafolio", "Tu consultor ve el detalle del riesgo de tu portafolio.",
    "Riesgo alto", "Riesgo medio", "Riesgo bajo",
  ]) assert.notEqual(traducir(es), null, es);
  assert.equal(traducir("9.35% del portafolio"), "9.35% of the portfolio");
  assert.equal(traducir("acciones: 89.8% del portafolio"), "stocks: 89.8% of the portfolio");
  assert.match(traducir("En 95% de los meses de los últimos 3 años la mezcla de hoy perdió menos que el VaR (los meses se ajustan a qué tan agitado está el mercado ahora); el CVaR es el promedio de los meses peores. Describe el pasado: no es una predicción ni un límite, y un golpe repentino del mercado puede superarlo."), /^In 95% of the months/);
});

test("frases que arma el backend con cifras y símbolos", () => {
  assert.equal(traducir("Buena tendencia: +23.7% en 6 meses y sobre su promedio de 200 días"), "Good trend: +23.7% in 6 months and above its 200-day average");
  assert.equal(traducir("CETES28 · CETES 28 días"), "CETES28 · CETES 28 days");
  assert.equal(traducir("Solo 3 acción(es) con 85% en acciones"), "Only 3 stock(s) with 85% in stocks");
  assert.equal(traducir("Credenciales inválidas"), "Invalid credentials");
});
