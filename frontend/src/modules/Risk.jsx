import { useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import StockSearch from "../components/StockSearch";
import { formatCurrency } from "../utils/format";

const TABS = [
  { id: "stock", label: "Una accion" },
  { id: "compare", label: "Comparar acciones" },
  { id: "portfolio", label: "Mi portafolio" },
];

const LEVEL_LABEL = { bajo: "Riesgo bajo", medio: "Riesgo medio", alto: "Riesgo alto" };
const COMPARE_COLORS = ["#c9971f", "#2f6fdb", "#0f7b3c", "#c1272d", "#7a4fd0"];
const MAX_COMPARE = 5;
const MEDIUM_FROM = 35;
const HIGH_FROM = 60;

const apiError = (err, fallback) => err.response?.data?.error ?? fallback;
const pct = (value) => (value == null ? "N/D" : `${value.toFixed(1)}%`);

function RiskBadge({ level, score }) {
  if (!level) return <span className="datil-period-tag">N/D</span>;
  return (
    <span className={`datil-risk datil-risk-${level}`}>
      {LEVEL_LABEL[level]} · {score}
    </span>
  );
}

// Barra 0-100 con las tres zonas del puntaje y un marcador en el valor.
function Meter({ score }) {
  return (
    <div
      className="datil-meter"
      role="img"
      aria-label={`Puntaje de riesgo ${score} de 100`}
    >
      <div className="datil-meter-zone datil-meter-low" style={{ width: `${MEDIUM_FROM}%` }} />
      <div className="datil-meter-zone datil-meter-mid" style={{ width: `${HIGH_FROM - MEDIUM_FROM}%` }} />
      <div className="datil-meter-zone datil-meter-high" style={{ width: `${100 - HIGH_FROM}%` }} />
      <div className="datil-meter-marker" style={{ left: `${Math.min(Math.max(score, 0), 100)}%` }} />
    </div>
  );
}

function formatFactorValue(factor) {
  if (factor.value == null) return "N/D";
  return `${factor.value}${factor.unit}`;
}

function FactorTable({ factors }) {
  return (
    <table className="datil-table">
      <thead>
        <tr>
          <th>Senal</th>
          <th className="datil-col-num">Valor</th>
          <th>Se considera</th>
          <th className="datil-col-num">Peso</th>
        </tr>
      </thead>
      <tbody>
        {factors.map((f) => (
          <tr key={f.id}>
            <td>{f.label}</td>
            <td className="datil-col-num">{formatFactorValue(f)}</td>
            <td>
              {f.available ? (
                <span className={`datil-risk datil-risk-${f.level}`}>{f.level}</span>
              ) : (
                <span className="datil-period-tag">sin datos suficientes</span>
              )}
              <span className="datil-period-tag">
                {" "}
                (bajo hasta {f.medium_from}
                {f.unit}, alto desde {f.high_from}
                {f.unit})
              </span>
            </td>
            <td className="datil-col-num">{f.weight}%</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const SCORE_EXPLANATION =
  "Mide que tanto suele caer una accion, con datos historicos hasta hoy. En pruebas con 10 anos de historia, las " +
  "acciones de riesgo alto tuvieron caidas de 30% o mas en el ano siguiente unas 2.5 veces mas seguido que las de " +
  "riesgo bajo. No predice si va a subir o bajar, y el pasado no garantiza el futuro. No es asesoria financiera.";

function StockRisk() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = (asset) => {
    setLoading(true);
    setError("");
    setData(null);
    apiClient
      .get(`/api/risk/stock/${encodeURIComponent(asset.symbol)}`)
      .then(({ data }) => setData(data))
      .catch((err) => setError(apiError(err, "No se pudo calcular el riesgo.")))
      .finally(() => setLoading(false));
  };

  return (
    <>
      <div className="datil-form-row">
        <label className="datil-field-wide">
          Accion
          <StockSearch onSelect={load} placeholder="Ej. Apple, Tesla, Toyota, Nestle..." />
        </label>
      </div>

      {loading && <p>Calculando riesgo...</p>}
      {error && <p className="datil-error">{error}</p>}

      {data && (
        <>
          <h3 className="datil-subheading">
            {data.symbol} · {data.name}
          </h3>
          <p className="datil-period-tag">
            {data.exchange} · cotiza en {data.currency} · datos al {data.as_of}
          </p>

          <div className="datil-risk-hero">
            <RiskBadge level={data.level} score={data.score} />
            <strong className={data.risky ? "datil-down" : "datil-up"}>
              {data.risky ? "Clasificada como riesgosa" : "No se clasifica como riesgosa"}
            </strong>
          </div>
          <Meter score={data.score} />

          <div className="datil-summary-grid">
            <div>
              <span className="datil-label">Rendimiento 12 meses (MXN)</span>
              <strong className={data.metrics.return_1y >= 0 ? "datil-up" : "datil-down"}>
                {pct(data.metrics.return_1y)}
              </strong>
            </div>
            <div>
              <span className="datil-label">Volatilidad en pesos</span>
              <strong>{pct(data.metrics.volatility)}</strong>
            </div>
            {data.metrics.volatility_native != null && data.currency !== "MXN" && (
              <div>
                <span className="datil-label">Volatilidad en {data.currency}</span>
                <strong>{pct(data.metrics.volatility_native)}</strong>
              </div>
            )}
          </div>

          <h3 className="datil-subheading">Por que este puntaje</h3>
          <FactorTable factors={data.factors} />
          {data.missing.length > 0 && (
            <p className="datil-period-tag">
              Sin datos suficientes para: {data.missing.join(", ")}. El puntaje se calculo con las demas senales.
            </p>
          )}
          <p className="datil-period-tag">{SCORE_EXPLANATION}</p>
        </>
      )}
    </>
  );
}

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
          Agregar accion ({symbols.length}/{MAX_COMPARE})
          <StockSearch key={searchKey} onSelect={add} placeholder="Busca por nombre o simbolo..." />
        </label>
      </div>

      {symbols.length > 0 && (
        <div className="datil-quick-pick-list">
          {symbols.map((s) => (
            <button key={s} className="datil-chip active" onClick={() => remove(s)} title="Quitar de la comparacion">
              <span className="datil-swatch" style={{ background: colorOf(s) }} /> {s} ×
            </button>
          ))}
        </div>
      )}
      {symbols.length === 1 && <p className="datil-period-tag">Agrega al menos una accion mas para comparar.</p>}

      {loading && <p>Comparando...</p>}
      {error && <p className="datil-error">{error}</p>}

      {result && (
        <>
          <h3 className="datil-subheading">Riesgo lado a lado</h3>
          <table className="datil-table">
            <thead>
              <tr>
                <th>Accion</th>
                <th>Moneda</th>
                <th>Riesgo</th>
                <th className="datil-col-num">Volatilidad</th>
                <th className="datil-col-num">Caida maxima</th>
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

          <h3 className="datil-subheading">Ultimo ano en pesos (inicio = 100)</h3>
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
        <p className="datil-error">No se pudo valuar alguna posicion; los porcentajes no la incluyen.</p>
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
          <span className="datil-label">Posicion mas grande</span>
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
        El riesgo de tus acciones es el promedio de sus puntajes, ponderado por cuanto tienes en cada una.
      </p>

      <h3 className="datil-subheading">Comportamiento historico del portafolio completo</h3>
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
              <span className="datil-label">Peor caida</span>
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
      <h3 className="datil-subheading">Que pasaria si...</h3>
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

      <h3 className="datil-subheading">Exposicion por moneda</h3>
      <div className="datil-quick-pick-list">
        {Object.entries(concentration.currency_exposure).map(([currency, share]) => (
          <span key={currency} className="datil-chip">
            {currency} {share}%
          </span>
        ))}
      </div>

      {stocks.positions.length > 0 && (
        <>
          <h3 className="datil-subheading">Riesgo por accion</h3>
          <table className="datil-table">
            <thead>
              <tr>
                <th>Accion</th>
                <th className="datil-col-num">% del portafolio</th>
                <th>Riesgo</th>
                <th className="datil-col-num">Volatilidad</th>
                <th className="datil-col-num">Caida maxima</th>
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
  const [tab, setTab] = useState("stock");

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

      {tab === "stock" && <StockRisk />}
      {tab === "compare" && <Compare />}
      {tab === "portfolio" && <PortfolioRisk />}
    </section>
  );
}

