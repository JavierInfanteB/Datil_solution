import { useAuth } from "../contexts/AuthContext";

export default function SessionWarning() {
  const { showWarning, extendSession, logout } = useAuth();

  if (!showWarning) return null;

  return (
    <div className="datil-modal-overlay">
      <div className="datil-modal" role="alertdialog" aria-modal="true" aria-labelledby="sw-titulo" aria-describedby="sw-texto">
        <h3 id="sw-titulo">Tu sesión está por expirar</h3>
        <p id="sw-texto">Por seguridad, se cerrará tu sesión en menos de un minuto por inactividad.</p>
        <div className="datil-actions">
          <button className="datil-btn datil-btn-primary" onClick={extendSession} autoFocus>
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
