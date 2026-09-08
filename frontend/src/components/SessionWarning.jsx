import { useAuth } from "../contexts/AuthContext";

export default function SessionWarning() {
  const { showWarning, extendSession, logout } = useAuth();

  if (!showWarning) return null;

  return (
    <div className="datil-modal-overlay">
      <div className="datil-modal">
        <h3>Tu sesion esta por expirar</h3>
        <p>Por seguridad, se cerrara tu sesion en menos de un minuto por inactividad.</p>
        <div className="datil-actions">
          <button className="datil-btn datil-btn-primary" onClick={extendSession}>
            Seguir conectado
          </button>
          <button className="datil-btn datil-btn-secondary" onClick={logout}>
            Salir ahora
          </button>
        </div>
      </div>
    </div>
  );
}
