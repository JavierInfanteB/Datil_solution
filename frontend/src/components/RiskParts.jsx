// Piezas del puntaje de riesgo compartidas por la pantalla de Riesgo y la de Comprar / Vender.
const LEVEL_LABEL = { bajo: "Riesgo bajo", medio: "Riesgo medio", alto: "Riesgo alto" };
const MEDIUM_FROM = 35;
const HIGH_FROM = 60;

export function RiskBadge({ level, score }) {
  if (!level) return <span className="datil-period-tag">N/D</span>;
  return (
    <span className={`datil-risk datil-risk-${level}`}>
      {LEVEL_LABEL[level]} · {score}
    </span>
  );
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
