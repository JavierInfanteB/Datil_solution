export function formatCurrency(value) {
  if (value == null) return "N/D";
  return `$${value.toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatPeriodLabel(period) {
  if (period === "1w") return "var. semanal";
  if (period === "1d") return "var. diaria";
  return "variacion";
}
