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

test("frases que arma el backend con cifras y símbolos", () => {
  assert.equal(traducir("Buena tendencia: +23.7% en 6 meses y sobre su promedio de 200 días"), "Good trend: +23.7% in 6 months and above its 200-day average");
  assert.equal(traducir("CETES28 · CETES 28 días"), "CETES28 · CETES 28 days");
  assert.equal(traducir("Solo 3 acción(es) con 85% en acciones"), "Only 3 stock(s) with 85% in stocks");
  assert.equal(traducir("Credenciales inválidas"), "Invalid credentials");
});
