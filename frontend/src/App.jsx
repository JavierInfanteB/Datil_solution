import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import ProtectedRoute from "./components/ProtectedRoute";
import SessionWarning from "./components/SessionWarning";
import DashboardPage from "./pages/DashboardPage";
import "./styles/datil-theme.css";

function App() {
  return (
    <ThemeProvider>
      {import.meta.env.VITE_DEMO && <div className="datil-demo-badge">Modo de pruebas · solo lectura</div>}
      <AuthProvider>
        <ProtectedRoute>
          <DashboardPage />
        </ProtectedRoute>
        <SessionWarning />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
