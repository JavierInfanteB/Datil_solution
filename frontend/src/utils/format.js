import { localeActual } from "../i18n/idioma.js";

export function formatCurrency(value) {
  if (value == null) return (localeActual() === "en-US" ? "N/A" : "N/D");
  const amount = Math.abs(value).toLocaleString(localeActual(), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${value < 0 ? "-" : ""}$${amount}`;
}

// Monto en la moneda de cotizacion de una accion (USD, EUR, JPY...). El codigo
// de moneda queda visible ("USD 347.10") para no confundirlo con pesos ($).
export function formatMoney(value, currency) {
  if (value == null) return (localeActual() === "en-US" ? "N/A" : "N/D");
  if (!currency || currency === "MXN") return formatCurrency(value);
  try {
    return value.toLocaleString(localeActual(), { style: "currency", currency, currencyDisplay: "code" });
  } catch {
    return `${value} ${currency}`;
  }
}

export function formatPeriodLabel(period) {
  const en = localeActual() === "en-US";
  if (period === "1w") return en ? "weekly chg." : "var. semanal";
  if (period === "1d") return en ? "daily chg." : "var. diaria";
  return en ? "change" : "variación";
}

// Fecha y hora locales de un instante ISO (los registros se guardan en UTC).
export function formatDateTime(iso) {
  return new Date(iso).toLocaleString(localeActual(), { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}
