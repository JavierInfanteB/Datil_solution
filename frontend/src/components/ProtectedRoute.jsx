import { useAuth } from "../contexts/AuthContext";
import Presentacion from "./Presentacion";

// El HTML del contenido protegido nunca se monta si no hay sesion: no es un
// "display:none", el arbol de React simplemente no lo incluye en el DOM.
export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <Presentacion />;
}
