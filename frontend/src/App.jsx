import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import ProtectedRoute from "./components/ProtectedRoute";
import AgentChat from "./components/AgentChat";
import SessionWarning from "./components/SessionWarning";
import DashboardPage from "./pages/DashboardPage";
import "./styles/datil-theme.css";
import "./styles/estilo-gbm.css";
import "./styles/chat.css";

// La key hace que la conversación empiece de cero al iniciar o cerrar sesión (cambia el tema del asistente).
function Chat() {
  const { isAuthenticated } = useAuth();
  return <AgentChat key={isAuthenticated ? "sesion" : "publico"} />;
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ProtectedRoute>
          <DashboardPage />
        </ProtectedRoute>
        <Chat />
        <SessionWarning />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
