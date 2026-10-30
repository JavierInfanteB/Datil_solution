import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import Logo from "./Logo";

export default function LoginForm() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err.response?.data?.error ?? "No se pudo iniciar sesión.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="datil-login-page">
      <form className="datil-login-card" onSubmit={handleSubmit}>
        <div className="datil-brand datil-brand-center">
          <Logo />
          <h1>Datil Solutions</h1>
        </div>
        <label>
          Usuario
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </label>
        <label>
          Contraseña
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="datil-error">{error}</p>}
        <button className="datil-btn datil-btn-primary" type="submit" disabled={loading}>
          {loading ? "Ingresando..." : "Iniciar sesión"}
        </button>
        {import.meta.env.VITE_DEMO && (
          <p className="datil-demo-hint">Cuenta de prueba: usuario <b>admin</b> · contraseña <b>admin</b>. Solo lectura.</p>
        )}
      </form>
    </div>
  );
}
