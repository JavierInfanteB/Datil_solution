import { useAuth } from "../contexts/AuthContext";
import Presentacion from "./Presentacion";

// El HTML del contenido protegido nunca se monta si no hay sesion: no es un
// "display:none", el arbol de React simplemente no lo incluye en el DOM.
export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Presentacion />;
  return (
    <>
      {/* La etiqueta de solo lectura va dentro de la plataforma, no en la carta de presentación */}
      {import.meta.env.VITE_DEMO && <div className="datil-demo-badge">Modo de pruebas · solo lectura</div>}
      {children}
    </>
  );
}
