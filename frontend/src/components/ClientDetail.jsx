import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { formatCurrency } from "../utils/format";
import { apiError, pct } from "../utils/risk";
import NotifyClient from "./NotifyClient";
import { PortfolioRiskDetail } from "./PortfolioRisk";
import { RiskBadge, SeverityTag } from "./RiskParts";

const SIDE_LABEL = { buy: "Compra", sell: "Venta", coupon: "Cupón", redeem: "Vencimiento" };
// Decisiones que piden mover algo: se mandan como acción sugerida; el resto, como aviso de riesgo.
const ACTION_IDS = new Set(["concentration", "risky_stock"]);

// Detalle de un cliente para su consultor: qué decisiones conviene tomar, qué tiene, cómo está de riesgo y,
// operación por operación, en qué contexto de riesgo compró y vendió.
export default function ClientDetail({ username, onBack }) {
  const [detail, setDetail] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [error, setError] = useState("");
  const [timelineError, setTimelineError] = useState("");
  const [draft, setDraft] = useState(null);

  // Precarga el formulario de aviso con una decisión sugerida y lleva hasta él.
  const notify = (d) => {
    setDraft({ kind: ACTION_IDS.has(d.id) ? "accion" : "riesgo", title: d.title.slice(0, 80), message: d.detail });
    document.getElementById("avisar")?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setTimeline(null);
    setError("");
    setTimelineError("");
    apiClient
      .get(`/api/consultant/clients/${username}`)
      .then(({ data }) => !cancelled && setDetail(data))
      .catch((err) => !cancelled && setError(apiError(err, "No se pudo cargar el cliente.")));
    apiClient
      .get(`/api/consultant/clients/${username}/timeline`)
      .then(({ data }) => !cancelled && setTimeline(data))
      .catch((err) => !cancelled && setTimelineError(apiError(err, "No se pudo analizar el historial.")));
    return () => {
      cancelled = true;
    };
  }, [username]);

  return (
    <>
      <div className="datil-actions">
        <button className="datil-btn datil-btn-secondary" onClick={onBack}>
          Volver a mis clientes
        </button>
      </div>
      {error && <p className="datil-error">{error}</p>}
      {!error && !detail && <p>Calculando el riesgo del cliente...</p>}
      {detail && <Overview detail={detail} onNotify={notify} />}
      {detail && <NotifyClient username={username} draft={draft} />}

      <section className="datil-card">
        <h2>Tiempos de compra y venta</h2>
        {timelineError && <p className="datil-error">{timelineError}</p>}
        {!timelineError && !timeline && <p>Analizando cada operación...</p>}
        {timeline && <Timeline rows={timeline} />}
      </section>
    </>
  );
}

function Overview({ detail, onNotify }) {
  const { client, portfolio, risk, decisions } = detail;
  return (
    <>
      <section className="datil-card">
        <h2>{client.name}</h2>
        <div className="datil-summary-grid">
          <div>
            <span className="datil-label">Patrimonio</span>
            <strong>{formatCurrency(portfolio.portfolio_total)}</strong>
          </div>
          <div>
            <span className="datil-label">Efectivo</span>
            <strong>{formatCurrency(portfolio.cash)}</strong>
          </div>
          <div>
            <span className="datil-label">Posiciones</span>
            <strong>{portfolio.holdings_count}</strong>
          </div>
        </div>

        <h3 className="datil-subheading">Decisiones que podrías tomar</h3>
        {risk.error ? (
          <p className="datil-period-tag">{risk.error}: no hay riesgo que reducir todavía.</p>
        ) : decisions.length === 0 ? (
          <p>Sin alertas: la cartera no rebasa ninguno de los límites de riesgo.</p>
        ) : (
          <ul className="datil-suggestions">
            {decisions.map((d, i) => (
              <li key={`${d.id}-${i}`}>
                <SeverityTag severity={d.severity} /> <strong>{d.title}</strong>
                <span className="datil-period-tag"> {d.detail} </span>
                <button className="datil-link" onClick={() => onNotify(d)}>
                  Enviar al cliente
                </button>
              </li>
            ))}
          </ul>
        )}
        <p className="datil-period-tag">
          Son ideas para reducir riesgo con datos históricos; la decisión es tuya y del cliente. No es asesoría financiera.
        </p>
      </section>

      {portfolio.holdings.length > 0 && (
        <section className="datil-card">
          <h2>Posiciones</h2>
          <div className="datil-table-wrap">
            <table className="datil-table">
              <thead>
                <tr>
                  <th>Activo</th>
                  <th className="datil-col-num">Cantidad</th>
                  <th className="datil-col-num">Valor</th>
                  <th className="datil-col-num">Ganancia o pérdida</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.holdings.map((h, i) => (
                  <tr key={`${h.symbol}-${h.lot_id ?? i}`}>
                    <td>
                      <strong>{h.symbol}</strong>
                      <span className="datil-period-tag"> {h.name}</span>
                    </td>
                    <td className="datil-col-num">{h.quantity}</td>
                    <td className="datil-col-num">{formatCurrency(h.value)}</td>
                    <td className={`datil-col-num ${h.gain_mxn >= 0 ? "datil-up" : "datil-down"}`}>
                      {h.gain_mxn != null ? `${formatCurrency(h.gain_mxn)} (${h.gain_percent}%)` : "N/D"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {!risk.error && (
        <section className="datil-card">
          <h2>Riesgo del portafolio</h2>
          <PortfolioRiskDetail data={risk} />
        </section>
      )}
    </>
  );
}

function Timeline({ rows }) {
  if (rows.length === 0) return <p>Este cliente todavía no tiene operaciones.</p>;
  return (
    <>
      <div className="datil-table-wrap">
        <table className="datil-table">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Operación</th>
              <th className="datil-col-num">Monto</th>
              <th className="datil-col-num">Lo tuvo</th>
              <th>Riesgo ese día</th>
              <th className="datil-col-num">Bajo su máximo anual</th>
              <th>Desde entonces</th>
              <th>Señales</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id}>
                <td>{t.date.slice(0, 10)}</td>
                <td>
                  {SIDE_LABEL[t.side] ?? t.side} <strong>{t.symbol}</strong>
                </td>
                <td className="datil-col-num">{formatCurrency(t.total_mxn)}</td>
                <td className="datil-col-num">{t.holding_days != null ? `${t.holding_days} días` : "N/D"}</td>
                <TimingCells trade={t} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="datil-period-tag">
        El riesgo de cada día usa el mismo puntaje que ve el cliente, calculado solo con lo que se sabía entonces. «Desde
        entonces» compara el precio en pesos de ese día con su peor punto posterior y con hoy. Es contexto, no un juicio
        de si la operación fue buena.
      </p>
    </>
  );
}

function TimingCells({ trade }) {
  const { timing } = trade;
  if (trade.type !== "accion") return <td colSpan={4} className="datil-period-tag">Bono: sin análisis de precio.</td>;
  if (!timing) return <td colSpan={4} className="datil-period-tag">Sin histórico de precios para esta fecha.</td>;
  return (
    <>
      <td>
        {timing.risk ? <RiskBadge level={timing.risk.level} score={timing.risk.score} /> : <span className="datil-period-tag">Sin historia suficiente</span>}
      </td>
      <td className="datil-col-num">{pct(timing.from_peak_pct)}</td>
      <td>
        peor {pct(timing.after.worst_pct)} · hoy {pct(timing.after.now_pct)}
      </td>
      <td>
        {timing.flags.map((flag) => (
          <div key={flag}>{flag}</div>
        ))}
      </td>
    </>
  );
}
