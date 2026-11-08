import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import Logo from "./Logo";

// Cuentas del demo público (solo lectura); los datos de prueba están en data/users.json.
const DEMO_ACCOUNTS = [
  { role: "Administrador", username: "admin", password: "admin", about: "Controla el sistema: usuarios, puestos y permisos." },
  { role: "Consultor", username: "consultor", password: "consultor", about: "Ve a sus clientes, su riesgo y les manda avisos." },
  { role: "Usuario", username: "usuario", password: "usuario", about: "Compra y vende, y ve su cartera, sus riesgos y los avisos de su consultor." },
];

export default function LoginForm({ enfocar = true }) {
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
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus={enfocar} />
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
          <div className="datil-demo-hint">
            <p>Cuentas de prueba, solo lectura. Toca una para llenar los datos:</p>
            <ul className="datil-demo-accounts">
              {DEMO_ACCOUNTS.map((a) => (
                <li key={a.username}>
                  <button
                    type="button"
                    className="datil-link"
                    onClick={() => {
                      setUsername(a.username);
                      setPassword(a.password);
                    }}
                  >
                    {a.role}
                  </button>{" "}
                  usuario <b>{a.username}</b> · contraseña <b>{a.password}</b>
                  <div>{a.about}</div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </form>
    </div>
  );
}
