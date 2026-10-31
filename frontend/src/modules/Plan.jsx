import { useEffect, useState } from "react";
import apiClient from "../api/client";
import AlertsPanel from "../components/AlertsPanel";
import NotesBox from "../components/NotesBox";
import Report, { Goals, withProgress } from "../components/Report";
import { apiError } from "../utils/risk";

// "Mi plan" del cliente, una sección por pestaña del menú: alertas, metas, notas para su consultor y reporte.
export default function Plan({ section }) {
  switch (section?.id) {
    case "metas":
      return <GoalsSection />;
    case "notas":
      return <NotesSection />;
    case "reporte":
      return (
        <section className="datil-card">
          <h2>Mi reporte</h2>
          <Report endpoint="/api/plan/report" />
        </section>
      );
    default:
      return (
        <section className="datil-card">
          <h2>Mis alertas</h2>
          <AlertsPanel
            url="/api/plan/alerts"
            hint="Pon cuánto quieres ganar o cuánto estás dispuesto a perder en una acción o en todo tu portafolio. Si no pones nada, no pasa nada: puedes agregar alertas cuando quieras. Tu consultor las ve y te avisamos aquí cuando se cumplan."
          />
        </section>
      );
  }
}

const EMPTY_GOAL = { title: "", target_mxn: "", target_date: "" };

function GoalsSection() {
  const [goals, setGoals] = useState(null);
  const [form, setForm] = useState(EMPTY_GOAL);
  const [error, setError] = useState("");

  const load = () =>
    Promise.all([apiClient.get("/api/plan/goals"), apiClient.get("/api/portfolio")])
      .then(([goals, portfolio]) => setGoals(withProgress(goals.data, portfolio.data.portfolio_total)))
      .catch((err) => setError(apiError(err, "No se pudieron cargar tus metas.")));

  useEffect(() => {
    load();
  }, []);

  const create = (e) => {
    e.preventDefault();
    setError("");
    apiClient
      .post("/api/plan/goals", { ...form, target_mxn: Number(form.target_mxn), target_date: form.target_date || undefined })
      .then(() => {
        setForm(EMPTY_GOAL);
        return load();
      })
      .catch((err) => setError(apiError(err, "No se pudo guardar la meta.")));
  };

  const field = (name) => ({ value: form[name], onChange: (e) => setForm({ ...form, [name]: e.target.value }) });

  return (
    <div className="datil-grid-2">
      <section className="datil-card">
        <h2>Mis metas</h2>
        <p className="datil-period-tag">Tu consultor ve tus metas para ayudarte a llegar a ellas.</p>
        {goals && goals.length === 0 && <p>Todavía no tienes metas.</p>}
        {goals && goals.length > 0 && <Goals goals={goals} onRemove={(g) => apiClient.delete(`/api/plan/goals/${g.id}`).then(load)} />}
      </section>
      <section className="datil-card">
        <h2>Nueva meta</h2>
        <form onSubmit={create}>
          <label>
            Meta
            <input {...field("title")} required maxLength={80} placeholder="Enganche de una casa" />
          </label>
          <label>
            Monto a alcanzar (MXN)
            <input type="number" min="1" step="any" {...field("target_mxn")} required />
          </label>
          <label>
            Fecha (opcional)
            <input type="date" {...field("target_date")} />
          </label>
          <div className="datil-actions">
            <button className="datil-btn datil-btn-primary">Guardar meta</button>
          </div>
        </form>
        {error && <p className="datil-error">{error}</p>}
      </section>
    </div>
  );
}

function NotesSection() {
  const [notes, setNotes] = useState(null);
  const load = () => apiClient.get("/api/plan/notes").then(({ data }) => setNotes(data));
  useEffect(() => {
    load();
  }, []);

  return (
    <section className="datil-card">
      <h2>Notas para mi consultor</h2>
      <p className="datil-period-tag">Lo que escribas aquí lo lee tu consultor: dudas, cambios en tu situación, lo que esperas.</p>
      {notes && <NotesBox notes={notes} url="/api/plan/notes" reload={load} placeholder="Voy a necesitar este dinero en un año..." />}
    </section>
  );
}
