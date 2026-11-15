export function formatCurrency(value) {
  if (value == null) return "N/D";
  const amount = Math.abs(value).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${value < 0 ? "-" : ""}$${amount}`;
}

// Monto en la moneda de cotizacion de una accion (USD, EUR, JPY...). El codigo
// de moneda queda visible ("USD 347.10") para no confundirlo con pesos ($).
export function formatMoney(value, currency) {
  if (value == null) return "N/D";
  if (!currency || currency === "MXN") return formatCurrency(value);
  try {
    return value.toLocaleString("es-MX", { style: "currency", currency, currencyDisplay: "code" });
  } catch {
    return `${value} ${currency}`;
  }
}

export function formatPeriodLabel(period) {
  if (period === "1w") return "var. semanal";
  if (period === "1d") return "var. diaria";
  return "variación";
}

// Fecha y hora locales de un instante ISO (los registros se guardan en UTC).
export function formatDateTime(iso) {
  return new Date(iso).toLocaleString("es-MX", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

// Porcentaje con un decimal; N/D cuando el dato no llegó.
export const pct = (value) => (value == null ? "N/D" : `${value.toFixed(1)}%`);

// Clase de color según el signo: verde (>= 0), rojo (< 0) y sin color cuando no hay dato.
// Antes, un N/D se pintaba de verde porque null >= 0 es verdadero.
export const trendClass = (value) => (value == null ? "" : value >= 0 ? "datil-up" : "datil-down");
