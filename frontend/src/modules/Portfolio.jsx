import { useEffect, useState } from "react";
import apiClient from "../api/client";
import CompositionPie, { slices } from "../components/CompositionPie";
import PortfolioRisk from "../components/PortfolioRisk";
import { formatCurrency, formatMoney, formatPeriodLabel } from "../utils/format";

// `client`: cartera de un cliente cuando la ve el admin; sin él, la propia.
export default function Portfolio({ client }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get("/api/portfolio", { params: client ? { client } : undefined })
      .then(({ data }) => setData(data))
      .catch(() => setError("No se pudo cargar la cartera."));
  }, [client]);

  if (error) return <p className="datil-error">{error}</p>;
  if (!data) return <p>Cargando cartera...</p>;

  const stocks = data.holdings.filter((h) => h.type === "accion");
  const bonds = data.holdings.filter((h) => h.type === "bono");

  return (
    <>
      <section className="datil-card">
        <h2>{client ? "Cartera del cliente" : "Mi cartera"}</h2>
        <p className="datil-label">
          Todo en pesos mexicanos (MXN).
          {Object.keys(data.fx_rates).length > 0 &&
            ` Tipos de cambio: ${Object.entries(data.fx_rates)
              .map(([currency, rate]) => `${currency} = $${rate}`)
              .join(" · ")}.`}
        </p>
        {data.incomplete && (
          <p className="datil-error">
            No se pudo valuar alguna acción; los totales no la incluyen. Intenta de nuevo en un momento.
          </p>
        )}

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
            <div className="datil-table-wrap">
              <table className="datil-table">
                <thead>
                  <tr>
                    <th>Símbolo</th>
                    <th>Nombre</th>
                    <th className="datil-col-num">Cantidad</th>
                    <th className="datil-col-num">Costo prom.</th>
                    <th className="datil-col-num">Precio</th>
                    <th className="datil-col-num">Variación</th>
                    <th className="datil-col-num">Total (MXN)</th>
                    <th className="datil-col-num">Ganancia (MXN)</th>
                  </tr>
                </thead>
                <tbody>
                  {stocks.map((h) => (
                    <tr key={h.symbol}>
                      <td>{h.symbol}</td>
                      <td>{h.name}</td>
                      <td className="datil-col-num">{h.quantity}</td>
                      <td className="datil-col-num">
                        {formatMoney(h.avg_cost, h.currency)}
                        {h.cost_estimated && <span className="datil-period-tag" title="Compra anterior al registro de costos: se estimó con el precio del día de la migración"> (est.)</span>}
                      </td>
                      <td className="datil-col-num">{formatMoney(h.price, h.currency)}</td>
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
                      <td className={`datil-col-num ${h.gain_mxn >= 0 ? "datil-up" : "datil-down"}`}>
                        {h.gain_mxn != null ? `${formatCurrency(h.gain_mxn)} (${h.gain_percent}%)` : "N/D"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {bonds.length > 0 && (
          <>
            <h3 className="datil-subheading">Bonos y CETES</h3>
            <div className="datil-table-wrap">
              <table className="datil-table">
                <thead>
                  <tr>
                    <th>Símbolo</th>
                    <th>Nombre</th>
                    <th className="datil-col-num">Títulos</th>
                    <th className="datil-col-num">Tasa contratada</th>
                    <th>Compra</th>
                    <th>Vence</th>
                    <th className="datil-col-num">Costo</th>
                    <th className="datil-col-num">Valor hoy</th>
                    <th className="datil-col-num">Ganancia</th>
                    <th className="datil-col-num">Si lo mantienes</th>
                    <th>Próximo cupón</th>
                  </tr>
                </thead>
                <tbody>
                  {bonds.map((h) => (
                    <tr key={h.lot_id ?? h.symbol + h.purchase_date}>
                      <td>{h.symbol}</td>
                      <td>{h.name}</td>
                      <td className="datil-col-num">{h.quantity}</td>
                      <td className="datil-col-num">{h.rate_at_purchase}%</td>
                      <td>{h.purchase_date}</td>
                      <td>{h.maturity_date}</td>
                      <td className="datil-col-num">{formatCurrency(h.cost)}</td>
                      <td className="datil-col-num">
                        {formatCurrency(h.value)}
                        <span
                          className="datil-period-tag"
                          title={
                            h.value_basis === "mercado"
                              ? "Lo que recibirías si lo vendes hoy, a las tasas de mercado de hoy"
                              : "Sin tasas de mercado disponibles: se muestra el valor devengado"
                          }
                        >
                          {" "}
                          ({h.value_basis})
                        </span>
                      </td>
                      <td className={`datil-col-num ${h.gain_mxn >= 0 ? "datil-up" : "datil-down"}`}>
                        {h.gain_mxn != null ? `${formatCurrency(h.gain_mxn)} (${h.gain_percent}%)` : "N/D"}
                      </td>
                      <td
                        className="datil-col-num"
                        title="Valor al vencimiento si lo mantienes: CETES pagan el nominal; el Bono M paga el nominal más sus cupones"
                      >
                        {formatCurrency(h.maturity_value)}
                      </td>
                      <td>
                        {h.next_coupon_date ? `${h.next_coupon_date} (${formatCurrency(h.coupon_amount)})` : "Sin cupones"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {stocks.length === 0 && bonds.length === 0 && <p className="datil-label">Aún no tienes activos en cartera.</p>}
      </section>
      {data.holdings.length > 0 && (
        <CompositionPie
          title={client ? "Cómo se reparte su cartera" : "Cómo se reparte mi cartera"}
          data={slices([...data.holdings.map((h) => ({ name: h.symbol, value: h.value })), { name: "Efectivo", value: data.cash }])}
        />
      )}
    {!client && (stocks.length > 0 || bonds.length > 0) && <PortfolioRisk />}
    </>
  );
}

