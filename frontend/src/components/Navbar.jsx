import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";

export default function Navbar({ modules, activeId, onSelect }) {
  const { user, logout } = useAuth();
  const { isDark, toggleTheme } = useTheme();

  return (
    <aside className="datil-sidebar">
      <div className="datil-brand">
        <span className="datil-logo">D</span>
        <div>
          <span className="datil-brand-name">Datil Solutions</span>
          <span className="datil-brand-tag">Gestión de inversiones</span>
        </div>
      </div>

      <nav className="datil-nav-links">
        {modules.map((mod) => (
          <button
            key={mod.id}
            className={mod.id === activeId ? "datil-nav-btn active" : "datil-nav-btn"}
            onClick={() => onSelect(mod.id)}
          >
            {mod.name}
          </button>
        ))}
      </nav>

      <div className="datil-nav-footer">
        <button className="datil-theme-toggle" onClick={toggleTheme}>
          {isDark ? "Tema claro" : "Tema oscuro"}
        </button>
        <div className="datil-user-card">
          <span className="datil-user-name">{user?.name}</span>
          <span className="datil-user-role">{user?.role === "admin" ? "Administrador" : "Usuario"}</span>
        </div>
        <button className="datil-btn datil-btn-secondary datil-btn-block" onClick={logout}>
          Cerrar sesión
        </button>
      </div>
    </aside>
  );
}
