import { useEffect, useRef, useState } from "react";
import apiClient from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { apiError } from "../utils/errors";

const MAX_PROMPT = 2000; // igual que el backend (modules/agent.py)
const MAX_HISTORY = 20;

// Una cosa a la vez: sin sesión contesta sobre Datil; con sesión, sobre métricas de bonos y acciones.
const MODES = {
  publico: {
    subtitle: "Preguntas sobre Datil Solutions",
    welcome: "Hola. Aquí puedes preguntar qué es Datil, qué instrumentos maneja y cómo funcionan sus avisos. Al iniciar sesión, el asistente explica las métricas de bonos y acciones.",
    placeholder: "Pregunta sobre Datil",
  },
  sesion: {
    subtitle: "Métricas de bonos y acciones",
    welcome: "Hola. Aquí puedes preguntar qué significan las métricas de bonos y acciones: puntaje de riesgo, beta, volatilidad, tasas, cupones. El asistente explica, no recomienda qué comprar o vender.",
    placeholder: "Pregunta sobre una métrica",
  },
};

// Botón flotante que abre el chat. App lo monta con key={modo}: al iniciar o cerrar sesión la conversación empieza de cero.
export default function AgentChat() {
  const { isAuthenticated } = useAuth();
  const mode = MODES[isAuthenticated ? "sesion" : "publico"];
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]); // { role: "user" | "model" | "error", text }
  const [text, setText] = useState("");
  const [waiting, setWaiting] = useState(false);
  const logRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open, waiting]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages, waiting]);

  const send = async (e) => {
    e.preventDefault();
    const prompt = text.trim();
    if (!prompt || waiting) return; // una pregunta a la vez
    // Al modelo solo le llegan los turnos completos (pregunta + respuesta), nunca los avisos de error.
    const history = messages
      .filter((m, i) => (m.role === "user" && messages[i + 1]?.role === "model") || m.role === "model")
      .slice(-MAX_HISTORY)
      .map((m) => ({ role: m.role, parts: [m.text] }));
    setMessages((prev) => [...prev, { role: "user", text: prompt }]);
    setText("");
    setWaiting(true);
    try {
      const { data } = await apiClient.post("/api/agent/ask", { prompt, history });
      setMessages((prev) => [...prev, { role: "model", text: data.response }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "error", text: apiError(err, "El asistente no pudo responder. Intenta de nuevo.") }]);
    } finally {
      setWaiting(false);
    }
  };

  return (
    <div className="datil-chat" onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
      {open && (
        <section className="datil-chat-panel" aria-label="Asistente de Datil">
          <header className="datil-chat-head">
            <div>
              <strong>Asistente Datil</strong>
              <span>{mode.subtitle}</span>
            </div>
            <button type="button" className="datil-chat-close" onClick={() => setOpen(false)} aria-label="Cerrar el asistente">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </button>
          </header>
          <div className="datil-chat-log" ref={logRef} role="log" aria-live="polite">
            <p className="datil-chat-msg datil-chat-model">{mode.welcome}</p>
            {messages.map((m, i) => (
              <p key={i} className={`datil-chat-msg datil-chat-${m.role}`} role={m.role === "error" ? "alert" : undefined}>
                {m.text}
              </p>
            ))}
            {waiting && <p className="datil-chat-msg datil-chat-model datil-chat-waiting">Escribiendo...</p>}
          </div>
          <form className="datil-chat-form" onSubmit={send}>
            <input
              ref={inputRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={MAX_PROMPT}
              placeholder={mode.placeholder}
              aria-label={mode.placeholder}
              disabled={waiting}
            />
            <button className="datil-btn datil-btn-primary" type="submit" disabled={waiting || !text.trim()}>
              Enviar
            </button>
          </form>
          <p className="datil-chat-note">Explica, no recomienda. No es asesoría financiera.</p>
        </section>
      )}
      <button type="button" className="datil-chat-fab" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-label={open ? "Cerrar el asistente" : "Abrir el asistente de Datil"}>
        <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 5h16v11H9l-5 4V5Z" />
          <path d="M8 9h8M8 12h5" />
        </svg>
      </button>
    </div>
  );
}
