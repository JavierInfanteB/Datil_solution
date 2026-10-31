import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { apiError } from "../utils/risk";

// Nivel de cada alerta (ver level_of en backend/utils/alerts.py): 3 cumplida, 2 al 80% del umbral, 1 al 60%.
export const LEVEL = {
  3: { label: "Cumplida", cls: "datil-risk-alto" },
  2: { label: "Cerca (80%)", cls: "datil-risk-medio" },
  1: { label: "Atención (60%)", cls: "datil-risk-medio" },
  0: { label: "Lejos", cls: "datil-risk-bajo" },
};
const INDICATION = { aviso: "Solo avisar", vender: "Considerar vender", comprar: "Considerar comprar más" };
const EMPTY = { symbol: "", kind: "loss", percent: "", indication: "aviso" };

export const ruleText = (a) => `${a.kind === "loss" ? "Pérdida" : "Ganancia"} de ${a.percent}%`;

// Alertas de ganancia o pérdida. Cada quien borra las que puso. `url`: /api/plan/alerts (el cliente) o
// /api/consultant/clients/<usuario>/alerts (el consultor, que las lee con `alerts` ya cargadas por su padre).
export default function AlertsPanel({ url, listUrl = url, hint }) {
  const { user: me } = useAuth();
  const [alerts, setAlerts] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [message, setMessage] = useState(null);

  const load = () =>
    apiClient
      .get(listUrl)
      .then(({ data }) => setAlerts(Array.isArray(data) ? data : data.alerts))
      .catch((err) => setMessage({ ok: false, text: apiError(err, "No se pudieron cargar las alertas.") }));

  useEffect(() => {
    load();
  }, [listUrl]);

  const run = (request) =>
    request()
      .then(() => {
        setMessage(null);
        return load();
      })
      .catch((err) => setMessage({ ok: false, text: apiError(err, "No se pudo guardar.") }));

  const create = (e) => {
    e.preventDefault();
    run(() => apiClient.post(url, { ...form, percent: Number(form.percent) })).then(() => setForm(EMPTY));
  };

  const field = (name) => ({ value: form[name], onChange: (e) => setForm({ ...form, [name]: e.target.value }) });

  return (
    <>
      {hint && <p className="datil-period-tag">{hint}</p>}
      {alerts && alerts.length === 0 && <p>Todavía no hay alertas.</p>}
      {alerts && alerts.length > 0 && (
        <div className="datil-table-wrap">
          <table className="datil-table">
            <thead>
              <tr>
                <th>Activo</th>
                <th>Regla</th>
                <th>Indicación</th>
                <th className="datil-col-num">Hoy</th>
                <th>Estado</th>
                <th>La puso</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {alerts.map((a) => (
                <tr key={a.id}>
                  <td>
                    <strong>{a.symbol === "*" ? "Todo el portafolio" : a.symbol}</strong>
                  </td>
                  <td>{ruleText(a)}</td>
                  <td>{INDICATION[a.indication]}</td>
                  <td className={`datil-col-num ${a.move == null ? "" : a.move >= 0 ? "datil-up" : "datil-down"}`}>
                    {a.move == null ? "N/D" : `${a.move > 0 ? "+" : ""}${a.move}%`}
                  </td>
                  <td>
                    <span className={`datil-risk ${LEVEL[a.level].cls}`}>{LEVEL[a.level].label}</span>
                  </td>
                  <td>{a.by === me.username ? "Tú" : a.by_role === "consultor" ? "Consultor" : "Cliente"}</td>
                  <td>
                    {a.by === me.username && (
                      <button className="datil-btn datil-btn-secondary" onClick={() => run(() => apiClient.delete(`${url}/${a.id}`))}>
                        Quitar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <form onSubmit={create}>
        <h3 className="datil-subheading">Nueva alerta</h3>
        <div className="datil-form-row">
          <label>
            Acción o bono (símbolo, * = todo)
            <input {...field("symbol")} required maxLength={20} placeholder="AAPL" />
          </label>
          <label>
            Avisar cuando haya
            <select {...field("kind")}>
              <option value="loss">Pérdida</option>
              <option value="gain">Ganancia</option>
            </select>
          </label>
          <label>
            Porcentaje
            <input type="number" min="0.1" step="0.1" {...field("percent")} required />
          </label>
          <label>
            Indicación
            <select {...field("indication")}>
              {Object.entries(INDICATION).map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="datil-actions">
          <button className="datil-btn datil-btn-primary">Crear alerta</button>
        </div>
      </form>
      {message && <p className={message.ok ? "datil-success" : "datil-error"}>{message.text}</p>}
    </>
  );
}
