// Pruebas del mensaje de error que ve el usuario. Se corren con: npm test
import assert from "node:assert/strict";
import { test } from "node:test";
import { apiError } from "./errors.js";

test("usa el mensaje que mandó el servidor", () => {
  assert.equal(apiError({ response: { data: { error: "Saldo insuficiente" } } }, "Ocurrió un error."), "Saldo insuficiente");
});

test("sin respuesta del servidor avisa que no hay conexión", () => {
  assert.match(apiError({ code: "ERR_NETWORK" }, "No se pudo guardar."), /conexión/);
  assert.match(apiError({ code: "ECONNABORTED" }, "No se pudo guardar."), /conexión/);
});

test("si no hay nada mejor, usa el texto de respaldo de la pantalla", () => {
  assert.equal(apiError({ response: { status: 500, data: {} } }, "No se pudo guardar."), "No se pudo guardar.");
  assert.equal(apiError(undefined, "Respaldo"), "Respaldo");
});
