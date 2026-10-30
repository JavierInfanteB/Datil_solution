import { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import Logo from "./Logo";

const ROLE_LABEL = { admin: "Administrador", consultor: "Consultor" };

export default function Navbar({ modules, active, onSelect }) {
  const { user, logout } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  // Solo aplica en celular: ahí el menú se pliega detrás del botón "Menú".
  const [menuOpen, setMenuOpen] = useState(false);

  const select = (mod, sectionId) => {
    onSelect(mod, sectionId);
    setMenuOpen(false);
  };

  return (
    <aside className={menuOpen ? "datil-sidebar open" : "datil-sidebar"}>
      <div className="datil-brand">
        <Logo />
        <div>
          <span className="datil-brand-name">Datil Solutions</span>
          <span className="datil-brand-tag">Gestión de inversiones</span>
        </div>
      </div>

      <button
        className="datil-menu-toggle"
        aria-expanded={menuOpen}
        aria-controls="datil-menu"
        onClick={() => setMenuOpen((open) => !open)}
      >
        {menuOpen ? "Cerrar" : "Menú"}
      </button>

      <div id="datil-menu" className="datil-menu">
        <nav className="datil-nav-links">
          {modules.map((mod) => {
            const isActive = mod.id === active.moduleId;
            return (
              <div key={mod.id} className="datil-nav-group">
                <button
                  className={isActive ? "datil-nav-btn active" : "datil-nav-btn"}
                  aria-current={isActive && mod.sections.length === 0 ? "page" : undefined}
                  onClick={() => (isActive ? setMenuOpen(false) : select(mod))}
                >
                  {mod.name}
                </button>
                {mod.sections.length > 0 && (
                  <div className="datil-nav-sub">
                    {mod.sections.map((s) => {
                      const isCurrent = isActive && s.id === active.sectionId;
                      return (
                        <button
                          key={s.id}
                          className={isCurrent ? "datil-nav-sub-btn active" : "datil-nav-sub-btn"}
                          aria-current={isCurrent ? "page" : undefined}
                          onClick={() => select(mod, s.id)}
                        >
                          {s.name}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        <div className="datil-nav-footer">
          <button className="datil-theme-toggle" onClick={toggleTheme}>
            {isDark ? "Tema claro" : "Tema oscuro"}
          </button>
          <div className="datil-user-card">
            <span className="datil-user-name">{user?.name}</span>
            <span className="datil-user-role">{ROLE_LABEL[user?.role] ?? "Usuario"}</span>
          </div>
          <button className="datil-btn datil-btn-secondary datil-btn-block" onClick={logout}>
            Cerrar sesión
          </button>
        </div>
      </div>
    </aside>
  );
}
