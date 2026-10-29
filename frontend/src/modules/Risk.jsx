import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import { RiskBadge } from "../components/RiskParts";
import StockSearch from "../components/StockSearch";
import { formatCurrency } from "../utils/format";
import { pct, SCORE_EXPLANATION } from "../utils/risk";

const TABS = [
  { id: "compare", label: "Comparar acciones" },
  { id: "portfolio", label: "Mi portafolio" },
];

const COMPARE_COLORS = ["#c9971f", "#2f6fdb", "#0f7b3c", "#c1272d", "#7a4fd0"];
const MAX_COMPARE = 5;

const apiError = (err, fallback) => err.response?.data?.error ?? fallback;

function Compare() {
  const [symbols, setSymbols] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searchKey, setSearchKey] = useState(0);

  const run = (list) => {
    setSymbols(list);
    setResult(null);
    setError("");
    if (list.length < 2) return;
    setLoading(true);
    apiClient
      .get("/api/risk/compare", { params: { symbols: list.join(",") } })
      .then(({ data }) => setResult(data))
      .catch((err) => {
        const failures = err.response?.data?.failures;
        const detail = failures ? ` ${Object.entries(failures).map(([s, m]) => `${s}: ${m}`).join(". ")}` : "";
        setError(apiError(err, "No se pudo comparar.") + detail);
      })
      .finally(() => setLoading(false));
  };

  const add = (asset) => {
    setSearchKey((k) => k + 1); // vacia el buscador para agregar otra
    if (symbols.includes(asset.symbol) || symbols.length >= MAX_COMPARE) return;
    run([...symbols, asset.symbol]);
  };

  const remove = (symbol) => run(symbols.filter((s) => s !== symbol));

  const colorOf = (symbol) => COMPARE_COLORS[symbols.indexOf(symbol) % COMPARE_COLORS.length];

  return (
    <>
      <div className="datil-form-row">
        <label className="datil-field-wide">
          Agregar acción ({symbols.length}/{MAX_COMPARE})
          <StockSearch key={searchKey} onSelect={add} placeholder="Busca por nombre o símbolo..." />
        </label>
      </div>

      {symbols.length > 0 && (
        <div className="datil-quick-pick-list">
          {symbols.map((s) => (
            <button key={s} className="datil-chip active" onClick={() => remove(s)} title="Quitar de la comparación">
              <span className="datil-swatch" style={{ background: colorOf(s) }} /> {s} ×
            </button>
          ))}
        </div>
      )}
      {symbols.length === 1 && <p className="datil-period-tag">Agrega al menos una acción más para comparar.</p>}

      {loading && <p>Comparando...</p>}
      {error && <p className="datil-error">{error}</p>}

      {result && (
        <>
          <h3 className="datil-subheading">Riesgo lado a lado</h3>
          <table className="datil-table">
            <thead>
              <tr>
                <th>Acción</th>
                <th>Moneda</th>
                <th>Riesgo</th>
                <th className="datil-col-num">Volatilidad</th>
                <th className="datil-col-num">Caída máxima</th>
                <th className="datil-col-num">Beta</th>
                <th className="datil-col-num">Rend. 12 meses</th>
              </tr>
            </thead>
            <tbody>
              {result.assessments.map((a) => (
                <tr key={a.symbol}>
                  <td>
                    <span className="datil-swatch" style={{ background: colorOf(a.symbol) }} />{" "}
                    <strong>{a.symbol}</strong>
                    <span className="datil-period-tag"> {a.name}</span>
                  </td>
                  <td>{a.currency}</td>
                  <td>
                    <RiskBadge level={a.level} score={a.score} />
                  </td>
                  <td className="datil-col-num">{pct(a.metrics.volatility)}</td>
                  <td className="datil-col-num">{pct(a.metrics.max_drawdown)}</td>
                  <td className="datil-col-num">{a.metrics.beta ?? "N/D"}</td>
                  <td className={`datil-col-num ${a.metrics.return_1y >= 0 ? "datil-up" : "datil-down"}`}>
                    {pct(a.metrics.return_1y)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {Object.keys(result.failures).length > 0 && (
            <p className="datil-error">
              No se pudieron incluir: {Object.entries(result.failures).map(([s, m]) => `${s} (${m})`).join(", ")}
            </p>
          )}

          <h3 className="datil-subheading">Último año en pesos (inicio = 100)</h3>
          <div className="datil-chart-wrapper">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={result.series}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--datil-border)" />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} />
                <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} width={50} />
                <Tooltip />
                <Legend />
                {result.assessments.map((a) => (
                  <Line
                    key={a.symbol}
                    type="monotone"
                    dataKey={a.symbol}
                    stroke={colorOf(a.symbol)}
                    dot={false}
                    strokeWidth={2}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="datil-period-tag">{SCORE_EXPLANATION}</p>
        </>
      )}
    </>
  );
}

function PortfolioRisk() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get("/api/risk/portfolio")
      .then(({ data }) => setData(data))
      .catch((err) => setError(apiError(err, "No se pudo calcular el riesgo del portafolio.")));
  }, []);

  if (error) return <p className="datil-error">{error}</p>;
  if (!data) return <p>Calculando riesgo del portafolio...</p>;

  const { stocks, history, concentration, scenarios } = data;

  return (
    <>
      {data.incomplete && (
        <p className="datil-error">No se pudo valuar alguna posición; los porcentajes no la incluyen.</p>
      )}

      <div className="datil-summary-grid">
        <div>
          <span className="datil-label">Acciones en tu portafolio</span>
          <strong>{stocks.share}%</strong>
        </div>
        <div>
          <span className="datil-label">Riesgo de tus acciones</span>
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
        El riesgo de tus acciones es el promedio de sus puntajes, ponderado por cuánto tienes en cada una.
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
              <span className="datil-label">Peor caída</span>
              <strong>{pct(history.max_drawdown)}</strong>
              <span className="datil-period-tag">
                {history.benchmark.symbol}: {pct(history.benchmark.max_drawdown)}
              </span>
            </div>
          </div>
          <p className="datil-period-tag">
            Con la mezcla de hoy mantenida de {history.from} a {history.to}, en pesos, incluyendo las acciones que
            suman {history.covers_pct_of_portfolio}% de tu portafolio. {history.benchmark.symbol} es un fondo de
            acciones de todo el mundo, como referencia de lo que hizo el mercado en el mismo periodo.
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
              <td className={`datil-col-num ${s.impact_mxn >= 0 ? "datil-up" : "datil-down"}`}>
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
                <th className="datil-col-num">Beta</th>
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

export default function Risk() {
  const [tab, setTab] = useState("compare");

  return (
    <section className="datil-card">
      <h2>Riesgo</h2>
      <div className="datil-tabs">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "datil-tab active" : "datil-tab"} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === "compare" && <Compare />}
      {tab === "portfolio" && <PortfolioRisk />}
    </section>
  );
}

