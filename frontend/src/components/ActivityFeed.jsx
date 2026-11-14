import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { formatCurrency, formatDateTime } from "../utils/format";
import { apiError } from "../utils/risk";

const ROLE = {
  usuario: { label: "Cliente", cls: "datil-risk-bajo" },
  consultor: { label: "Consultor", cls: "datil-risk-medio" },
  admin: { label: "Administrador", cls: "datil-risk-alto" },
};
const ORIGIN = {
  cliente: "App del cliente",
  admin: "Administrador, en nombre del cliente",
  "orden programada": "Orden programada",
  automático: "Automático",
};

// Registro con fecha y hora. kind="operaciones": cada compra o venta, quién la hizo y por dónde. kind="avisos": lo que
// los consultores mandaron a sus clientes. Lo que ve cada quien lo decide el servidor; `filter` ({consultant, client})
// solo acota lo que ya llegó.
export default function ActivityFeed({ kind = "operaciones", filter = {}, title }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [role, setRole] = useState("todos");
  const notices = kind === "avisos";

  useEffect(() => {
    setRows(null);
    apiClient
      .get("/api/activity", { params: { kind } })
      .then(({ data }) => setRows(data))
      .catch((err) => setError(apiError(err, "No se pudo cargar el registro.")));
  }, [kind]);

  const scoped = rows
    ? rows.filter((r) => (!filter.client || r.client_username === filter.client) && (!filter.consultant || r.consultant === filter.consultant))
    : [];
  const roles = Object.keys(ROLE).filter((r) => scoped.some((x) => x.role === r));
  const shown = scoped.filter((r) => role === "todos" || r.role === role);

  return (
    <section className="datil-card">
      <h2>{title ?? (notices ? "Avisos enviados" : "Registro de operaciones")}</h2>
      {error && <p className="datil-error" role="alert">{error}</p>}
      {!error && !rows && <p>Cargando...</p>}
      {rows && scoped.length === 0 && <p className="datil-period-tag">Sin registros con estos filtros.</p>}
      {!notices && roles.length > 1 && (
        <div className="datil-lapse-bar" role="group" aria-label="Quién lo hizo">
          {["todos", ...roles].map((r) => (
            <button key={r} className={r === role ? "datil-chip active" : "datil-chip"} aria-pressed={r === role} onClick={() => setRole(r)}>
              {r === "todos" ? "Todos" : ROLE[r].label}
            </button>
          ))}
        </div>
      )}
      {shown.length > 0 && (
        <div className="datil-table-wrap" tabIndex={0}>
          <table className="datil-table">
            <thead>
              <tr>
                <th>Fecha y hora</th>
                <th>{notices ? "Consultor" : "Quién"}</th>
                {!notices && <th>Por dónde</th>}
                <th>{notices ? "Aviso" : "Qué hizo"}</th>
                <th>Cliente</th>
                <th className={notices ? undefined : "datil-col-num"}>{notices ? "Estado" : "Monto"}</th>
              </tr>
            </thead>
            <tbody>
              {shown.slice(0, 30).map((e, i) => (
                <tr key={`${e.date}-${i}`}>
                  <td>{formatDateTime(e.date)}</td>
                  <td>
                    <span className={`datil-risk ${ROLE[e.role].cls}`}>{ROLE[e.role].label}</span> {e.actor}
                  </td>
                  {!notices && <td>{ORIGIN[e.origin] ?? e.origin}</td>}
                  <td>{e.text}</td>
                  <td>{e.client}</td>
                  <td className={notices ? undefined : "datil-col-num"}>{notices ? (e.read ? "Leído" : "Sin leer") : formatCurrency(e.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
