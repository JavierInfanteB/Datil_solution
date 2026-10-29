import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import apiClient from "../api/client";
import { apiError, pct, SCORE_EXPLANATION } from "../utils/risk";
import { RiskBadge } from "./RiskParts";
import StockSearch from "./StockSearch";

const COMPARE_COLORS = ["#c9971f", "#2f6fdb", "#0f7b3c", "#c1272d", "#7a4fd0"];
const MAX_COMPARE = 5;

// Compara el riesgo de hasta 5 acciones (GET /api/risk/compare). `initial` las deja ya elegidas.
export default function StockCompare({ initial = [] }) {
  const [symbols, setSymbols] = useState(initial);
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
