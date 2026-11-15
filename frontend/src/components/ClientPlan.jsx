import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { apiError } from "../utils/risk";
import NotesBox from "./NotesBox";
import Report, { Goals, withProgress } from "./Report";

// Lo que el consultor ve y escribe de un cliente: sus metas, las notas que le dejó, sus notas personales
// (solo él las lee) y el reporte por periodo. Las alertas viven con las sugerencias.
export default function ClientPlan({ username }) {
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState("");
  const base = `/api/consultant/clients/${username}`;

  const load = () =>
    apiClient
      .get(`${base}/plan`)
      .then(({ data }) => setPlan(data))
      .catch((err) => setError(apiError(err, "No se pudo cargar el plan del cliente.")));

  useEffect(() => {
    setPlan(null);
    load();
  }, [username]);

  if (error) return <p className="datil-error" role="alert">{error}</p>;
  if (!plan) return null;

  return (
    <>
      <section className="datil-card">
        <h2>Metas y notas del cliente</h2>
        <h3 className="datil-subheading">Metas</h3>
        {plan.goals.length === 0 ? <p className="datil-period-tag">Aún no ha puesto metas.</p> : <Goals goals={withProgress(plan.goals, plan.portfolio_total)} />}
        <h3 className="datil-subheading">Notas que te dejó</h3>
        <NotesBox notes={plan.notes} />
        <h3 className="datil-subheading">Mis notas personales (el cliente no las ve)</h3>
        <NotesBox notes={plan.private_notes} url={`${base}/private-notes`} reload={load} placeholder="Cómo es el cliente, qué conviene hablar con él..." />
      </section>

      <section className="datil-card">
        <h2>Reporte del cliente</h2>
        <Report endpoint={`${base}/report`} />
      </section>
    </>
  );
}
