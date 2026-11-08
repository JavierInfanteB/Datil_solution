import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import ProtectedRoute from "./components/ProtectedRoute";
import SessionWarning from "./components/SessionWarning";
import DashboardPage from "./pages/DashboardPage";
import "./styles/datil-theme.css";
import "./styles/estilo-gbm.css";

function App() {
  return (
    <ThemeProvider>
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
