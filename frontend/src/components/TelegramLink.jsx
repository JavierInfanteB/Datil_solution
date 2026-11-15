import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { apiError } from "../utils/errors";

// Enlazar Telegram para recibir ahí los mismos avisos de la bandeja. Dos pasos: abrir el bot con el enlace
// (lleva el código del usuario) y tocar Iniciar; luego confirmar aquí. Si el servidor no tiene bot, no se muestra.
export default function TelegramLink() {
  const [status, setStatus] = useState(null); // { available, linked, url }
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiClient.get("/api/notifications/telegram").then(({ data }) => setStatus(data)).catch(() => {});
  }, []);

  if (!status?.available) return null;

  const call = (method) => async () => {
    setError("");
    setBusy(true);
    try {
      const { data } = await apiClient[method]("/api/notifications/telegram");
      setStatus(data);
    } catch (err) {
      setError(apiError(err, "No se pudo completar. Intenta de nuevo."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="datil-card" aria-labelledby="telegram-titulo">
      <h2 id="telegram-titulo">Avisos por Telegram</h2>
      {status.linked ? (
        <>
          <p>Tu Telegram está conectado: los avisos de esta bandeja te llegan también ahí.</p>
          <button type="button" className="datil-btn datil-btn-secondary" onClick={call("delete")} disabled={busy}>
            Desconectar Telegram
          </button>
        </>
      ) : (
        <>
          <p>Recibe en Telegram los mismos avisos que llegan a esta bandeja.</p>
          <ol className="datil-steps">
            <li>
              {status.url ? (
                <a className="datil-link" href={status.url} target="_blank" rel="noreferrer">Abre el bot de Datil en Telegram</a>
              ) : (
                "El bot no responde por ahora; intenta más tarde"
              )}{" "}
              y toca <strong>Iniciar</strong>.
            </li>
            <li>Vuelve aquí y confirma.</li>
          </ol>
          <button type="button" className="datil-btn datil-btn-primary" onClick={call("post")} disabled={busy || !status.url}>
            {busy ? "Buscando tu mensaje..." : "Ya toqué Iniciar"}
          </button>
        </>
      )}
      {error && <p className="datil-error" role="alert">{error}</p>}
    </section>
  );
}
