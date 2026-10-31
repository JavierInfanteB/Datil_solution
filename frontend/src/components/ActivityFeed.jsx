import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { formatCurrency } from "../utils/format";
import { apiError } from "../utils/risk";

const ROLE = {
  usuario: { label: "Cliente", cls: "datil-risk-bajo" },
  consultor: { label: "Consultor", cls: "datil-risk-medio" },
  admin: { label: "Administrador", cls: "datil-risk-alto" },
};

// Actividad reciente: lo que ve cada quien lo decide el servidor (el admin todo, el consultor lo de sus clientes y lo suyo).
// Los filtros solo ofrecen los roles que aparecen.
export default function ActivityFeed({ title = "Actividad reciente" }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [role, setRole] = useState("todos");

  useEffect(() => {
    apiClient
      .get("/api/activity")
      .then(({ data }) => setRows(data))
      .catch((err) => setError(apiError(err, "No se pudo cargar la actividad.")));
  }, []);

  const roles = rows ? Object.keys(ROLE).filter((r) => rows.some((x) => x.role === r)) : [];
  const shown = rows ? rows.filter((r) => role === "todos" || r.role === role) : [];

  return (
    <section className="datil-card">
      <h2>{title}</h2>
      {error && <p className="datil-error">{error}</p>}
      {!error && !rows && <p>Cargando...</p>}
      {rows && rows.length === 0 && <p className="datil-period-tag">Todavía no hay actividad.</p>}
      {roles.length > 1 && (
        <div className="datil-lapse-bar" role="group" aria-label="Quién lo hizo">
          {["todos", ...roles].map((r) => (
            <button key={r} className={r === role ? "datil-chip active" : "datil-chip"} aria-pressed={r === role} onClick={() => setRole(r)}>
              {r === "todos" ? "Todos" : ROLE[r].label}
            </button>
          ))}
        </div>
      )}
      {shown.length > 0 && (
        <div className="datil-table-wrap">
          <table className="datil-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Quién</th>
                <th>Qué hizo</th>
                <th>Cliente</th>
                <th className="datil-col-num">Monto</th>
              </tr>
            </thead>
            <tbody>
              {shown.slice(0, 25).map((e, i) => (
                <tr key={`${e.date}-${i}`}>
                  <td>{e.date.slice(0, 10)}</td>
                  <td>
                    <span className={`datil-risk ${ROLE[e.role].cls}`}>{ROLE[e.role].label}</span> {e.actor}
                  </td>
                  <td>{e.text}</td>
                  <td>{e.client}</td>
                  <td className="datil-col-num">{e.amount == null ? "" : formatCurrency(e.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
