// Los catálogos del frontend deben coincidir con los ids del backend. Se corren con: npm test
import assert from "node:assert/strict";
import { test } from "node:test";
import { KIND_LABEL } from "./avisos.js";
import { GLOSSARY } from "./glossary.js";
import { REINVEST_LABEL } from "./reinvest.js";

test("tipos de aviso (backend/utils/notifications.py)", () => {
  assert.deepEqual(Object.keys(KIND_LABEL).sort(), ["accion", "alerta", "aviso", "riesgo"]);
});

test("modos de reinversión (backend/utils/bond_engine.py)", () => {
  assert.deepEqual(Object.keys(REINVEST_LABEL).sort(), ["all", "none", "same"]);
});

test("el glosario no tiene definiciones vacías", () => {
  for (const [term, text] of Object.entries(GLOSSARY)) assert.ok(text.length > 20, `definición muy corta: ${term}`);
});
