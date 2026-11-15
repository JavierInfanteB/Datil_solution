import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { formatCurrency, trendClass } from "../utils/format";
import { apiError, pct, SCORE_EXPLANATION } from "../utils/risk";
import { GLOSSARY } from "../utils/glossary";
import { RiskBadge, RiskLevelTag } from "./RiskParts";
import Term from "./Term";

// Riesgo de todo el portafolio (GET /api/risk/portfolio): puntaje de las acciones, comportamiento histórico, VaR, estrés,
// escenarios y concentración. Si el usuario no tiene el módulo de riesgo, no muestra nada. El cliente solo recibe el nivel
// (bajo, medio o alto): el detalle lo ve su consultor.
export default function PortfolioRisk() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    apiClient
      .get("/api/risk/portfolio")
      .then(({ data }) => setData(data))
      .catch((err) =>
        err.response?.status === 403
          ? setForbidden(true)
          : setError(apiError(err, "No se pudo calcular el riesgo del portafolio.")),
      );
  }, []);

  if (forbidden) return null;

  return (
    <section className="datil-card">
      <h2>Riesgo del portafolio</h2>
      {error && <p className="datil-error" role="alert">{error}</p>}
      {!error && !data && <p>Calculando riesgo del portafolio...</p>}
      {data?.summary_only && <PortfolioRiskLevel level={data.level} />}
      {data && !data.summary_only && <PortfolioRiskDetail data={data} />}
    </section>
  );
}

export function PortfolioRiskLevel({ level }) {
  if (!level) return <p>Todavía no hay acciones en tu portafolio para medir su riesgo.</p>;
  return (
    <>
      <div className="datil-summary-grid">
        <div>
          <span className="datil-label">Nivel de riesgo de tu portafolio</span>
          <strong>
            <RiskLevelTag level={level} />
          </strong>
        </div>
      </div>
      <p className="datil-period-tag">Tu consultor ve el detalle del riesgo de tu portafolio.</p>
    </>
  );
}

export function PortfolioRiskDetail({ data }) {
  const { stocks, history, concentration, scenarios } = data;

  return (
    <>
      {data.incomplete && (
        <p className="datil-error" role="alert">No se pudo valuar alguna posición; los porcentajes no la incluyen.</p>
      )}

      <div className="datil-summary-grid">
        <div>
          <span className="datil-label">Acciones en el portafolio</span>
          <strong>{stocks.share}%</strong>
        </div>
        <div>
          <span className="datil-label">Riesgo de las acciones</span>
          <strong>
            <RiskBadge level={stocks.level} score={stocks.weighted_score} />
          </strong>
        </div>
        <div>
          <span className="datil-label">Posición más grande</span>
          <strong>
            {concentration.largest_position.symbol} · {concentration.largest_position.share}%
          </strong>
        </div>
        <div>
          <span className="datil-label">Efectivo</span>
          <strong>{concentration.cash_share}%</strong>
        </div>
      </div>
      <p className="datil-period-tag">
        El riesgo de las acciones es el promedio de sus puntajes, ponderado por cuánto hay en cada una.
      </p>

      <h3 className="datil-subheading">Comportamiento histórico del portafolio completo</h3>
      {history?.error && <p className="datil-period-tag">{history.error}</p>}
      {history && !history.error && (
        <>
          <div className="datil-summary-grid">
            <div>
              <span className="datil-label">Volatilidad anual</span>
              <strong>{pct(history.volatility)}</strong>
              <span className="datil-period-tag">
                {history.benchmark.symbol}: {pct(history.benchmark.volatility)}
              </span>
            </div>
            <div>
              <span className="datil-label">Pérdida en los peores días</span>
              <strong>{pct(history.tail_loss)}</strong>
              <span className="datil-period-tag">
                {history.benchmark.symbol}: {pct(history.benchmark.tail_loss)}
              </span>
            </div>
            <div>
              <span className="datil-label">Peor caída</span>
              <strong>{pct(history.max_drawdown)}</strong>
              <span className="datil-period-tag">
                {history.benchmark.symbol}: {pct(history.benchmark.max_drawdown)}
              </span>
            </div>
          </div>
          {history.var && (
            <>
              <div className="datil-summary-grid">
                <div>
                  <span className="datil-label"><Term text={GLOSSARY.var}>Pérdida en un mal mes (VaR)</Term></span>
                  <strong>{formatCurrency(history.var.var_mxn)}</strong>
                  <span className="datil-period-tag">{`${pct(history.var.var_percent)} del portafolio`}</span>
                </div>
                <div>
                  <span className="datil-label"><Term text={GLOSSARY.cvar}>Pérdida en los peores meses (CVaR)</Term></span>
                  <strong>{formatCurrency(history.var.cvar_mxn)}</strong>
                  <span className="datil-period-tag">{`${pct(history.var.cvar_percent)} del portafolio`}</span>
                </div>
              </div>
              <p className="datil-period-tag">
                {`En ${history.var.confidence}% de los meses de los últimos 3 años la mezcla de hoy perdió menos que el VaR (los meses se ajustan a qué tan agitado está el mercado ahora); el CVaR es el promedio de los meses peores. Describe el pasado: no es una predicción ni un límite, y un golpe repentino del mercado puede superarlo.`}
              </p>
            </>
          )}
          <p className="datil-period-tag">
            Con la mezcla de hoy mantenida de {history.from} → {history.to}, en pesos, incluyendo las acciones que
            suman {history.covers_pct_of_portfolio}% del portafolio. {history.benchmark.symbol} es un fondo de
            acciones de todo el mundo, como referencia de lo que hizo el mercado en el mismo periodo.
          </p>
        </>
      )}
      {data.stress?.error && <p className="datil-period-tag">{data.stress.error}</p>}
      {data.stress && !data.stress.error && (
        <>
          <h3 className="datil-subheading">Si el mercado repitiera su peor mes</h3>
          <div className="datil-summary-grid">
            <div>
              <span className="datil-label"><Term text={GLOSSARY.estres}>Pérdida estresada</Term></span>
              <strong>{formatCurrency(data.stress.loss_mxn)}</strong>
              <span className="datil-period-tag">{`${pct(data.stress.loss_percent)} del portafolio`}</span>
            </div>
            <div>
              <span className="datil-label">Peor mes del mercado global</span>
              <strong>{pct(data.stress.market_worst_percent)}</strong>
              <span className="datil-period-tag">{`${data.stress.from} → ${data.stress.to}`}</span>
            </div>
            <div>
              <span className="datil-label"><Term text={GLOSSARY.beta}>Beta del portafolio</Term></span>
              <strong>{data.stress.beta}</strong>
              <span className="datil-period-tag">{`acciones: ${data.stress.covers_pct_of_portfolio}% del portafolio`}</span>
            </div>
          </div>
          <p className="datil-period-tag">
            Es lo que perdería la mezcla de hoy si el mercado global repitiera su peor mes desde 2008, según la beta de sus acciones (bonos y efectivo
            se tratan como estables). Es un peor caso histórico de mercado, no un límite: no incluye el tipo de cambio ni lo que le pase a una empresa en
            particular, que puede caer más que el mercado por algo suyo. En pruebas con carteras de 5 acciones habría cubierto el crash de 2020 en 96 de cada 100 casos.
          </p>
        </>
      )}
      <h3 className="datil-subheading">Qué pasaría si...</h3>
      <table className="datil-table">
        <thead>
          <tr>
            <th>Escenario</th>
            <th className="datil-col-num">Impacto (MXN)</th>
            <th className="datil-col-num">% del portafolio</th>
          </tr>
        </thead>
        <tbody>
          {scenarios.map((s) => (
            <tr key={s.id}>
              <td>{s.label}</td>
              <td className={`datil-col-num ${trendClass(s.impact_mxn)}`}>
                {formatCurrency(s.impact_mxn)}
              </td>
              <td className="datil-col-num">{s.impact_percent}%</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 className="datil-subheading">Exposición por moneda</h3>
      <div className="datil-quick-pick-list">
        {Object.entries(concentration.currency_exposure).map(([currency, share]) => (
          <span key={currency} className="datil-chip">
            {currency} {share}%
          </span>
        ))}
      </div>

      {stocks.positions.length > 0 && (
        <>
          <h3 className="datil-subheading">Riesgo por acción</h3>
          <table className="datil-table">
            <thead>
              <tr>
                <th>Acción</th>
                <th className="datil-col-num">% del portafolio</th>
                <th>Riesgo</th>
                <th className="datil-col-num">Volatilidad</th>
                <th className="datil-col-num">Caída máxima</th>
                <th className="datil-col-num">
                  <Term text={GLOSSARY.beta}>Beta</Term>
                </th>
              </tr>
            </thead>
            <tbody>
              {stocks.positions.map((p) => (
                <tr key={p.symbol}>
                  <td>
                    <strong>{p.symbol}</strong>
                    <span className="datil-period-tag"> {p.name}</span>
                  </td>
                  <td className="datil-col-num">{p.weight}%</td>
                  <td>{p.error ? <span className="datil-period-tag">{p.error}</span> : <RiskBadge level={p.level} score={p.score} />}</td>
                  <td className="datil-col-num">{pct(p.metrics?.volatility)}</td>
                  <td className="datil-col-num">{pct(p.metrics?.max_drawdown)}</td>
                  <td className="datil-col-num">{p.metrics?.beta ?? "N/D"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {data.notes.map((note) => (
        <p key={note} className="datil-period-tag">
          {note}
        </p>
      ))}
      <p className="datil-period-tag">{SCORE_EXPLANATION}</p>
    </>
  );
}
