import { useAuth } from "../contexts/AuthContext";
import LoginForm from "./LoginForm";

// El HTML del contenido protegido nunca se monta si no hay sesion: no es un
// "display:none", el arbol de React simplemente no lo incluye en el DOM.
export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <LoginForm />;
}
