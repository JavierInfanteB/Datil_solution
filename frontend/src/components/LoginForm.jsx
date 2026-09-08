import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";

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
      setError(err.response?.data?.error ?? "No se pudo iniciar sesion.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="datil-login-page">
      <form className="datil-login-card" onSubmit={handleSubmit}>
        <div className="datil-brand datil-brand-center">
          <span className="datil-logo">D</span>
          <h1>Datil Solutions</h1>
        </div>
        <label>
          Usuario
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </label>
        <label>
          Contrasena
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <p className="datil-error">{error}</p>}
        <button className="datil-btn datil-btn-primary" type="submit" disabled={loading}>
          {loading ? "Ingresando..." : "Iniciar sesion"}
        </button>
      </form>
    </div>
  );
}
