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
