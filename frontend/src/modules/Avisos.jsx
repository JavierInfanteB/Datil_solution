import { useEffect, useState } from "react";
import apiClient from "../api/client";
import KindTag from "../components/KindTag";
import { apiError } from "../utils/risk";

// Bandeja del usuario: lo que su consultor le manda (riesgos, acciones sugeridas, avisos). Los avisos
// nuevos se ven marcados en esta visita y quedan como leídos al abrirla.
export default function Avisos({ onUnreadChange }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get("/api/notifications")
      .then(({ data }) => {
        if (cancelled) return;
        setData(data);
        // En el modo de pruebas (solo lectura) el servidor rechaza esto y no pasa nada: siguen como nuevos.
        data.items.filter((n) => !n.read).forEach((n) => apiClient.post(`/api/notifications/${n.id}/read`).catch(() => {}));
        onUnreadChange?.(0);
      })
      .catch((err) => !cancelled && setError(apiError(err, "No se pudieron cargar los avisos.")));
    return () => {
      cancelled = true;
    };
  }, [onUnreadChange]);

  return (
    <section className="datil-card">
      <h2>Avisos de mi consultor</h2>
      {error && <p className="datil-error">{error}</p>}
      {!error && !data && <p>Cargando avisos...</p>}
      {data && data.items.length === 0 && <p>Tu consultor aún no te ha mandado avisos.</p>}
      {data && data.items.length > 0 && (
        <>
          <p className="datil-period-tag">
            Tus riesgos y tus acciones los ves en Mi Cartera y en Comprar / Vender; aquí llega lo que tu consultor
            quiere que revises.
          </p>
          <ul className="datil-suggestions">
            {data.items.map((n) => (
              <li key={n.id}>
                <KindTag kind={n.kind} />{" "}
                {!n.read && <span className="datil-risk datil-risk-medio">Nuevo</span>} <strong>{n.title}</strong>
                <span className="datil-period-tag">
                  {" "}
                  {n.date.slice(0, 10)} · {n.from_name}
                </span>
                <div className="datil-notice-text">{n.message}</div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
