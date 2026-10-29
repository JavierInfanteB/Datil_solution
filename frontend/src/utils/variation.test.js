// Pruebas del cálculo de variación. Se corren con: npm test
import assert from "node:assert/strict";
import { test } from "node:test";
import { addMonths, lapseStart, lapseVariation, LAPSES, periodVariations, sliceLapse } from "./variation.js";

const series = (...pairs) => pairs.map(([date, close]) => ({ date, close }));
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} != ${expected}`);
const lapse = (id) => LAPSES.find((l) => l.id === id);

test("por día: cada cierre contra el anterior, el primero contra la base del lapso", () => {
  const points = series(["2026-10-01", 100], ["2026-10-02", 110], ["2026-10-05", 99], ["2026-10-06", 99]);
  const rows = periodVariations(points, "dia", { from: "2026-10-01", today: "2026-10-06" });
  assert.deepEqual(rows.map((r) => r.label), ["2 oct 2026", "5 oct 2026", "6 oct 2026"]);
  near(rows[0].percent, 10);
  near(rows[0].change, 10);
  near(rows[1].percent, -10);
  near(rows[1].change, -11);
  near(rows[2].percent, 0);
  assert.ok(rows.every((r) => !r.partialStart && !r.partialEnd));
});

test("quincena: el 15 cierra la primera y el 16 abre la segunda", () => {
  const points = series(
    ["2026-09-30", 100],
    ["2026-10-14", 105],
    ["2026-10-15", 110],
    ["2026-10-16", 121],
    ["2026-10-31", 132],
  );
  const rows = periodVariations(points, "quincena", { from: "2026-09-30", today: "2026-11-02" });
  assert.deepEqual(rows.map((r) => r.label), ["1-15 oct 2026", "16-31 oct 2026"]);
  assert.deepEqual(rows.map((r) => [r.start, r.end]), [["2026-10-01", "2026-10-15"], ["2026-10-16", "2026-10-31"]]);
  near(rows[0].percent, 10); // 110 contra la base 100
  near(rows[1].percent, 20); // 132 contra el cierre del 15 (110)
});

test("quincena: la segunda de febrero termina en 28, o en 29 en año bisiesto", () => {
  const last = (date) => periodVariations(series(["2026-01-31", 1], [date, 2]), "quincena", { from: "2026-01-31", today: "2030-01-01" })[0];
  assert.equal(last("2026-02-20").label, "16-28 feb 2026");
  assert.equal(last("2026-02-20").end, "2026-02-28");
  assert.equal(last("2028-02-20").label, "16-29 feb 2028");
});

test("mes: encadena con el último cierre del mes anterior", () => {
  const points = series(["2026-08-31", 200], ["2026-09-15", 210], ["2026-09-30", 220], ["2026-10-30", 198]);
  const rows = periodVariations(points, "mes", { from: "2026-08-31", today: "2026-11-01" });
  assert.deepEqual(rows.map((r) => r.label), ["sep 2026", "oct 2026"]);
  near(rows[0].percent, 10);
  near(rows[1].change, -22);
  near(rows[1].percent, -10);
});

test("periodo incompleto al inicio: el lapso arranca a mitad de mes", () => {
  const points = series(["2026-09-17", 100], ["2026-09-30", 104], ["2026-10-30", 130]);
  const rows = periodVariations(points, "mes", { from: "2026-09-17", today: "2026-11-01" });
  assert.deepEqual(rows.map((r) => r.partialStart), [true, false]);
  near(rows[0].percent, 4); // solo cuenta desde el 17 de septiembre
});

test("periodo incompleto al final: el mes en curso se marca, el que ya terminó no", () => {
  const points = series(["2026-09-30", 100], ["2026-10-15", 105], ["2026-10-28", 108]);
  assert.equal(periodVariations(points, "mes", { from: "2026-09-30", today: "2026-10-28" })[0].partialEnd, true);
  assert.equal(periodVariations(points, "mes", { from: "2026-09-30", today: "2026-10-31" })[0].partialEnd, false);
  // La primera quincena de octubre ya terminó el 28; la segunda sigue en curso
  const rows = periodVariations(points, "quincena", { from: "2026-09-30", today: "2026-10-28" });
  assert.deepEqual(rows.map((r) => r.partialEnd), [false, true]);
});

test("un fin de semana no cuenta como periodo en curso si el mes ya terminó", () => {
  // Viernes 30 de octubre fue el último cierre; hoy es sábado 31
  const points = series(["2026-09-30", 100], ["2026-10-30", 110]);
  assert.equal(periodVariations(points, "mes", { from: "2026-09-30", today: "2026-10-31" })[0].partialEnd, false);
});

test("la base es el último cierre en la fecha de inicio o antes (fin de semana)", () => {
  // from es sábado 3 de octubre: la base es el cierre del viernes 2
  const points = series(["2026-10-01", 90], ["2026-10-02", 100], ["2026-10-05", 110]);
  assert.deepEqual(sliceLapse(points, "2026-10-03").map((p) => p.date), ["2026-10-02", "2026-10-05"]);
  const rows = periodVariations(points, "mes", { from: "2026-10-03", today: "2026-10-31" });
  near(rows[0].percent, 10);
  // la quincena 16-31 de otro mes no se marca incompleta al inicio si la base cae antes de su primer día
  const q = periodVariations(series(["2026-10-15", 100], ["2026-10-19", 101]), "quincena", { from: "2026-10-16", today: "2026-11-05" });
  assert.equal(q[0].partialStart, false);
});

test("semestre y año respetan los límites naturales", () => {
  const points = series(["2025-12-31", 100], ["2026-06-30", 110], ["2026-07-01", 121], ["2026-12-31", 132], ["2027-01-04", 130]);
  const semesters = periodVariations(points, "semestre", { from: "2025-12-31", today: "2027-02-01" });
  assert.deepEqual(semesters.map((r) => r.label), ["ene-jun 2026", "jul-dic 2026", "ene-jun 2027"]);
  near(semesters[0].percent, 10);
  near(semesters[1].percent, 20); // 132 contra 110
  const years = periodVariations(points, "anio", { from: "2025-12-31", today: "2027-02-01" });
  assert.deepEqual(years.map((r) => r.label), ["2026", "2027"]);
  near(years[0].percent, 32);
  assert.equal(years[1].partialEnd, true);
});

test("sin historia antes del inicio, la base es el primer punto", () => {
  const points = series(["2026-10-05", 50], ["2026-10-06", 55]);
  const rows = periodVariations(points, "dia", { from: "2026-09-01", today: "2026-10-06" });
  assert.equal(rows.length, 1);
  near(rows[0].percent, 10);
});

test("casos vacíos y base en cero", () => {
  assert.deepEqual(periodVariations([], "dia", { from: "2026-10-01", today: "2026-10-02" }), []);
  assert.deepEqual(periodVariations(series(["2026-10-01", 5]), "dia", { from: "2026-10-01", today: "2026-10-02" }), []);
  const rows = periodVariations(series(["2026-10-01", 0], ["2026-10-02", 3]), "dia", { from: "2026-10-01", today: "2026-10-02" });
  assert.equal(rows[0].percent, null);
  near(rows[0].change, 3);
  assert.equal(lapseVariation([], "2026-10-01"), null);
});

test("variación de todo el lapso", () => {
  const points = series(["2026-09-28", 100], ["2026-10-10", 90], ["2026-10-28", 125]);
  const v = lapseVariation(points, "2026-09-28");
  near(v.percent, 25);
  near(v.change, 25);
});

test("inicio del lapso: meses sin ese día caen en el último día del mes", () => {
  assert.equal(addMonths("2026-03-31", -1), "2026-02-28");
  assert.equal(addMonths("2028-03-31", -1), "2028-02-29");
  assert.equal(addMonths("2026-01-15", -1), "2025-12-15");
  assert.equal(lapseStart("2026-10-28", lapse("1S")), "2026-10-21");
  assert.equal(lapseStart("2026-10-28", lapse("1M")), "2026-09-28");
  assert.equal(lapseStart("2026-10-28", lapse("1A")), "2025-10-28");
});

test("granularidades por lapso", () => {
  assert.deepEqual(lapse("1M").grains, ["dia", "quincena", "mes"]);
  assert.deepEqual(lapse("1A").grains, ["mes", "semestre", "anio"]);
});
