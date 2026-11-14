// Mensaje de error para mostrar al usuario a partir de una excepción de axios.
// Prioridad: el mensaje que mandó el servidor; si no hubo respuesta (servidor caído, sin red),
// un texto que lo dice claro; y si no, el texto de respaldo de cada pantalla.
export function apiError(err, fallback) {
  const fromServer = err?.response?.data?.error;
  if (fromServer) return fromServer;
  if (err && !err.response && (err.code === "ERR_NETWORK" || err.code === "ECONNABORTED")) {
    return "No hay conexión con el servidor. Revisa tu internet e intenta de nuevo.";
  }
  return fallback;
}
