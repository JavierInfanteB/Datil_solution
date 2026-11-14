// Pruebas de formato y color de tendencia. Se corren con: npm test
import assert from "node:assert/strict";
import { test } from "node:test";
import { formatCurrency, formatMoney, formatPeriodLabel, pct, trendClass } from "./format.js";

test("formatCurrency: pesos con dos decimales y signo antes del $", () => {
  assert.equal(formatCurrency(1234.5), "$1,234.50");
  assert.equal(formatCurrency(-22.1), "-$22.10");
  assert.equal(formatCurrency(0), "$0.00");
});

test("formatCurrency: sin dato se muestra N/D, no $0.00", () => {
  assert.equal(formatCurrency(null), "N/D");
  assert.equal(formatCurrency(undefined), "N/D");
});

test("formatMoney: otra moneda deja el código visible; pesos usa el formato normal", () => {
  assert.equal(formatMoney(null, "USD"), "N/D");
  assert.equal(formatMoney(10, "MXN"), "$10.00");
  assert.equal(formatMoney(10, undefined), "$10.00");
  assert.match(formatMoney(347.1, "USD"), /USD/);
});

test("formatMoney: un código de moneda inválido no rompe la pantalla", () => {
  assert.equal(formatMoney(5, "??"), "5 ??");
});

test("formatPeriodLabel", () => {
  assert.equal(formatPeriodLabel("1w"), "var. semanal");
  assert.equal(formatPeriodLabel("1d"), "var. diaria");
  assert.equal(formatPeriodLabel("otro"), "variación");
});

test("pct: un decimal y N/D sin dato", () => {
  assert.equal(pct(12.345), "12.3%");
  assert.equal(pct(0), "0.0%");
  assert.equal(pct(null), "N/D");
});

test("trendClass: verde, rojo y sin color cuando no hay dato", () => {
  assert.equal(trendClass(5), "datil-up");
  assert.equal(trendClass(0), "datil-up");
  assert.equal(trendClass(-0.01), "datil-down");
  assert.equal(trendClass(null), "");
  assert.equal(trendClass(undefined), "");
});
