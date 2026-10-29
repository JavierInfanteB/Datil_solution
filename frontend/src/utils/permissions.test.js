// Pruebas de la regla de permisos por módulo/sección. Se corren con: npm test
import assert from "node:assert/strict";
import { test } from "node:test";
import { isGranted } from "./permissions.js";

test("el módulo completo concede todas sus secciones", () => {
  assert.ok(isGranted(["trading"], "trading"));
  assert.ok(isGranted(["trading"], "trading.bono"));
});

test("una sección sola concede ver el módulo pero no las otras secciones", () => {
  assert.ok(isGranted(["trading.accion"], "trading"));
  assert.ok(isGranted(["trading.accion"], "trading.accion"));
  assert.ok(!isGranted(["trading.accion"], "trading.bono"));
});

test("no confunde módulos con prefijo parecido", () => {
  assert.ok(!isGranted(["trading"], "trade"));
  assert.ok(!isGranted(["trade.x"], "trading"));
  assert.ok(!isGranted([], "portfolio"));
});
