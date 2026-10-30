// Piezas del puntaje de riesgo compartidas por Comprar / Vender, la comparación y el riesgo del portafolio.
import { pct, SCORE_EXPLANATION } from "../utils/risk";

const LEVEL_LABEL = { bajo: "Riesgo bajo", medio: "Riesgo medio", alto: "Riesgo alto" };
// Mismos cortes que MEDIUM_FROM / HIGH_FROM en backend/utils/risk_engine.py.
const MEDIUM_FROM = 30;
const HIGH_FROM = 55;

export function RiskBadge({ level, score }) {
  if (!level) return <span className="datil-period-tag">N/D</span>;
  return (
    <span className={`datil-risk datil-risk-${level}`}>
      {LEVEL_LABEL[level]} · {score}
    </span>
  );
}

// Prioridad de una sugerencia del consultor (alta / media / baja), con los colores de los niveles de riesgo.
const SEVERITY_LEVEL = { alta: "alto", media: "medio", baja: "bajo" };

export function SeverityTag({ severity }) {
  return <span className={`datil-risk datil-risk-${SEVERITY_LEVEL[severity]}`}>{severity}</span>;
}

// Barra 0-100 con las tres zonas del puntaje y un marcador en el valor.
export function Meter({ score }) {
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

// Detalle completo del riesgo de una acción (respuesta de GET /api/risk/stock): cifras clave,
// desglose por señal y la advertencia de qué mide y qué no.
export function StockRiskDetail({ data }) {
  return (
    <>
      <p className="datil-period-tag">
        {data.exchange} · cotiza en {data.currency} · datos al {data.as_of}
      </p>

      <div className="datil-summary-grid">
        <div>
          <span className="datil-label">Caída máxima (3 años, MXN)</span>
          <strong>{pct(data.metrics.max_drawdown)}</strong>
        </div>
        <div>
          <span className="datil-label">Pérdida en los peores días</span>
          <strong>{pct(data.metrics.tail_loss)}</strong>
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

      <h3 className="datil-subheading">Por qué este puntaje</h3>
      <FactorTable factors={data.factors} />
      {data.missing.length > 0 && (
        <p className="datil-period-tag">
          Sin datos suficientes para: {data.missing.join(", ")}. El puntaje se calculó con las demás señales.
        </p>
      )}
      <p className="datil-period-tag">{SCORE_EXPLANATION}</p>
    </>
  );
}

export function FactorTable({ factors }) {
  return (
    <table className="datil-table">
      <thead>
        <tr>
          <th>Señal</th>
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
