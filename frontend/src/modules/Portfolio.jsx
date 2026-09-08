import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { formatCurrency, formatPeriodLabel } from "../utils/format";

export default function Portfolio() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get("/api/portfolio")
      .then(({ data }) => setData(data))
      .catch(() => setError("No se pudo cargar la cartera."));
  }, []);

  if (error) return <p className="datil-error">{error}</p>;
  if (!data) return <p>Cargando cartera...</p>;

  const stocks = data.holdings.filter((h) => h.type === "accion");
  const bonds = data.holdings.filter((h) => h.type === "bono");

  return (
    <section className="datil-card">
      <h2>Mi cartera</h2>

      <div className="datil-summary-grid">
        <div>
          <span className="datil-label">Total invertido</span>
          <strong>{formatCurrency(data.invested_total)}</strong>
        </div>
        <div>
          <span className="datil-label">Sin invertir</span>
          <strong>{formatCurrency(data.cash)}</strong>
        </div>
        <div>
          <span className="datil-label">Total en cartera</span>
          <strong>{formatCurrency(data.portfolio_total)}</strong>
        </div>
        <div>
          <span className="datil-label">Activos distintos</span>
          <strong>{data.holdings_count}</strong>
        </div>
      </div>

      {stocks.length > 0 && (
        <>
          <h3 className="datil-subheading">Acciones</h3>
          <table className="datil-table">
            <thead>
              <tr>
                <th>Simbolo</th>
                <th>Nombre</th>
                <th className="datil-col-num">Cantidad</th>
                <th className="datil-col-num">Precio</th>
                <th className="datil-col-num">Variacion</th>
                <th className="datil-col-num">Total</th>
              </tr>
            </thead>
            <tbody>
              {stocks.map((h) => (
                <tr key={h.symbol}>
                  <td>{h.symbol}</td>
                  <td>{h.name}</td>
                  <td className="datil-col-num">{h.quantity}</td>
                  <td className="datil-col-num">{h.price ?? "N/D"}</td>
                  <td className={`datil-col-num ${h.change_percent >= 0 ? "datil-up" : "datil-down"}`}>
                    {h.change_percent != null ? (
                      <>
                        {h.change_percent >= 0 ? "\u25B2" : "\u25BC"} {h.change_percent}%
                        <span className="datil-period-tag"> ({formatPeriodLabel(h.change_period)})</span>
                      </>
                    ) : (
                      "N/D"
                    )}
                  </td>
                  <td className="datil-col-num">{formatCurrency(h.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {bonds.length > 0 && (
        <>
          <h3 className="datil-subheading">Bonos y CETES</h3>
          <table className="datil-table">
            <thead>
              <tr>
                <th>Simbolo</th>
                <th>Nombre</th>
                <th className="datil-col-num">Titulos</th>
                <th className="datil-col-num">Tasa contratada</th>
                <th>Compra</th>
                <th>Vence</th>
                <th className="datil-col-num">Valor devengado</th>
              </tr>
            </thead>
            <tbody>
              {bonds.map((h) => (
                <tr key={h.symbol + h.purchase_date}>
                  <td>{h.symbol}</td>
                  <td>{h.name}</td>
                  <td className="datil-col-num">{h.quantity}</td>
                  <td className="datil-col-num">{h.rate_at_purchase}%</td>
                  <td>{h.purchase_date}</td>
                  <td>{h.maturity_date}</td>
                  <td className="datil-col-num">{formatCurrency(h.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {stocks.length === 0 && bonds.length === 0 && <p className="datil-label">Aun no tienes activos en cartera.</p>}
    </section>
  );
}

