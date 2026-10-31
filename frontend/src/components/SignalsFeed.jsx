import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { formatDateTime } from "../utils/format";
import { apiError } from "../utils/risk";
import AlertsPanel from "./AlertsPanel";
import { RiskBadge, SeverityTag } from "./RiskParts";

const TYPES = [
  ["todas", "Todas"],
  ["sugerencia", "Sugerencias"],
  ["alerta", "Alertas"],
];
const signed = (v) => (v == null ? "N/D" : `${v > 0 ? "+" : ""}${v}%`);

// Sugerencias y alertas de los clientes en un solo lugar, ordenadas por la fecha y hora en que aparecieron. Cualquiera
// puede mandarse al cliente como aviso (se prepara el aviso y se lleva a Avisos, al final del menú).
export default function SignalsFeed({ filter, onOptions, onOpen, onNotice }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [type, setType] = useState("todas");
  const [state, setState] = useState("activa");
  const [byStock, setByStock] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    apiClient
      .get("/api/consultant/feed", { params: { client: filter.client || undefined } })
      .then(({ data }) => {
        if (cancelled) return;
        setData(data);
        if (!filter.client) onOptions(data.clients);
      })
      .catch((err) => !cancelled && setError(apiError(err, "No se pudieron cargar las sugerencias y alertas.")));
    return () => {
      cancelled = true;
    };
  }, [filter.client]);

  if (error) return <p className="datil-error">{error}</p>;
  if (!data) return <p>Calculando el riesgo de tus clientes... la primera vez puede tardar unos segundos.</p>;

  const items = data.items.filter((i) => (type === "todas" || i.kind === type) && i.status === state);
  const count = (kind) => data.items.filter((i) => i.kind === kind && i.status === "activa").length;
  const notice = (i) =>
    onNotice({
      username: i.username,
      kind: i.kind === "alerta" ? "riesgo" : i.severity === "alta" ? "accion" : "riesgo",
      title: i.title.slice(0, 80),
      message: i.detail,
    });

  const groups = {};
  if (byStock) for (const i of items) (groups[i.symbol ?? "Portafolio completo"] ??= []).push(i);

  return (
    <>
      <section className="datil-card">
        <h2>Sugerencias y alertas</h2>
        <div className="datil-summary-grid">
          <div>
            <span className="datil-label">Sugerencias activas</span>
            <strong>{count("sugerencia")}</strong>
          </div>
          <div>
            <span className="datil-label">Alertas activas</span>
            <strong>{count("alerta")}</strong>
          </div>
          <div>
            <span className="datil-label">De prioridad alta</span>
            <strong>{data.items.filter((i) => i.status === "activa" && i.severity === "alta").length}</strong>
          </div>
        </div>
        <div className="datil-lapse-bar" role="group" aria-label="Tipo">
          {TYPES.map(([id, label]) => (
            <button key={id} className={id === type ? "datil-chip active" : "datil-chip"} aria-pressed={id === type} onClick={() => setType(id)}>
              {label}
            </button>
          ))}
          <span className="datil-period-tag">·</span>
          {[
            ["activa", "Activas"],
            ["resuelta", "Resueltas"],
          ].map(([id, label]) => (
            <button key={id} className={id === state ? "datil-chip active" : "datil-chip"} aria-pressed={id === state} onClick={() => setState(id)}>
              {label}
            </button>
          ))}
          <span className="datil-period-tag">·</span>
          <button className={byStock ? "datil-chip active" : "datil-chip"} aria-pressed={byStock} onClick={() => setByStock(!byStock)}>
            Agrupar por acción
          </button>
        </div>

        {items.length === 0 && <p className="datil-period-tag">Nada con estos filtros.</p>}
        {byStock ? (
          Object.entries(groups).map(([symbol, list], n) => (
            <details key={symbol} open={n < 3}>
              <summary>
                <strong>{symbol}</strong>
                <span className="datil-period-tag"> {list.length}</span>
              </summary>
              <List items={list} onOpen={onOpen} onNotice={notice} />
            </details>
          ))
        ) : (
          <List items={items} onOpen={onOpen} onNotice={notice} />
        )}
        <p className="datil-period-tag datil-section-note">
          Cada una lleva la fecha y hora en que apareció; si deja de cumplirse pasa a Resueltas. Son ideas con datos históricos, no asesoría
          financiera.
        </p>
      </section>

      <Ideas />

      <details>
        <summary>
          <strong>Alertas de un cliente</strong>
          <span className="datil-period-tag"> ponerlas o quitarlas</span>
        </summary>
        <AlertsConfig clients={data.clients} initial={filter.client} />
      </details>
    </>
  );
}

function List({ items, onOpen, onNotice }) {
  return (
    <ul className="datil-suggestions">
      {items.map((i) => (
        <li key={`${i.kind}-${i.username}-${i.id}`}>
          <span className="datil-period-tag">{formatDateTime(i.when)}</span>
          <SeverityTag severity={i.severity} /> <span className="datil-chip">{i.kind === "alerta" ? "Alerta" : "Sugerencia"}</span>{" "}
          <button className="datil-link" onClick={() => onOpen(i.username)}>
            {i.client}
          </button>
          : <strong>{i.title}</strong>
          <span className="datil-period-tag">{i.detail}</span>
          {i.status === "activa" && (
            <button className="datil-link" onClick={() => onNotice(i)}>
              Enviar como aviso
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}

function AlertsConfig({ clients, initial }) {
  const [client, setClient] = useState(initial ?? "");
  return (
    <>
      <label>
        Cliente
        <select value={client} onChange={(e) => setClient(e.target.value)}>
          <option value="">Elige un cliente</option>
          {clients.map((c) => (
            <option key={c.username} value={c.username}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      {client && (
        <AlertsPanel
          key={client}
          url={`/api/consultant/clients/${client}/alerts`}
          listUrl={`/api/consultant/clients/${client}/plan`}
          hint="Las del cliente avisan a él al cumplirse; tú las ves desde el 60% y el 80% de su umbral. Las que pongas tú solo las ves tú."
        />
      )}
    </>
  );
}

// Ideas de acciones de riesgo bajo: filtro con datos del pasado, no una predicción.
function Ideas() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get("/api/consultant/ideas")
      .then(({ data }) => setData(data))
      .catch((err) => setError(apiError(err, "No se pudieron cargar las ideas de acciones.")));
  }, []);

  return (
    <section className="datil-card">
      <h2>Ideas de acciones de riesgo bajo</h2>
      {error && <p className="datil-error">{error}</p>}
      {!error && !data && <p>Revisando acciones...</p>}
      {data && data.ideas.length === 0 && <p>Ninguna de las {data.reviewed} acciones revisadas cumple hoy.</p>}
      {data && data.ideas.length > 0 && (
        <div className="datil-table-wrap">
          <table className="datil-table">
            <thead>
              <tr>
                <th>Acción</th>
                <th>Riesgo</th>
                <th className="datil-col-num">Sobre su mínimo</th>
                <th className="datil-col-num">Bajo su máximo</th>
                <th className="datil-col-num">6 meses</th>
                <th>Por qué aparece</th>
              </tr>
            </thead>
            <tbody>
              {data.ideas.map((i) => (
                <tr key={i.symbol}>
                  <td>
                    <strong>{i.symbol}</strong>
                    <span className="datil-period-tag"> {i.name}</span>
                  </td>
                  <td>
                    <RiskBadge level={i.risk.level} score={i.risk.score} />
                  </td>
                  <td className="datil-col-num">{signed(i.facts.above_low_pct)}</td>
                  <td className="datil-col-num">{signed(i.facts.below_high_pct)}</td>
                  <td className={`datil-col-num ${i.facts.change_6m_pct >= 0 ? "datil-up" : "datil-down"}`}>{signed(i.facts.change_6m_pct)}</td>
                  <td style={{ whiteSpace: "normal" }}>{i.reasons.join(" · ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="datil-period-tag datil-section-note">
        Acciones de una lista de seguimiento con riesgo bajo (el mismo puntaje que ven los clientes) que están cerca de su mínimo de los últimos
        años o con buena tendencia. Es un filtro con datos del pasado, no una predicción: no dice que vayan a subir.
      </p>
    </section>
  );
}
