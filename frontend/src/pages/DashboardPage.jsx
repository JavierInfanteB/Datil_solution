import { Suspense, useEffect, useState } from "react";
import apiClient from "../api/client";
import { getAvailableModules } from "../modules/moduleRegistry";
import Navbar from "../components/Navbar";

export default function DashboardPage() {
  const [modules, setModules] = useState(null);
  const [active, setActive] = useState({ moduleId: null, sectionId: null });
  const [error, setError] = useState("");
  const [unread, setUnread] = useState(0); // avisos sin leer del usuario, para el contador del menú

  // Abrir un módulo sin sección elegida cae en su primera sección permitida.
  const open = (mod, sectionId = mod?.sections[0]?.id ?? null) => setActive({ moduleId: mod?.id ?? null, sectionId });

  useEffect(() => {
    apiClient
      .get("/api/permissions/me")
      .then(({ data }) => {
        const available = getAvailableModules(data.modules);
        setModules(available);
        open(available[0]);
        if (available.some((m) => m.id === "avisos")) {
          apiClient.get("/api/notifications").then(({ data }) => setUnread(data.unread)).catch(() => {});
        }
      })
      .catch(() => setError("No se pudieron cargar tus permisos."));
  }, []);

  if (error) return <p className="datil-error" role="alert">{error}</p>;
  if (!modules) return <p role="status">Cargando tu plataforma...</p>;

  const activeModule = modules.find((m) => m.id === active.moduleId);
  const ActiveModule = activeModule?.Component;
  const activeSection = activeModule?.sections.find((s) => s.id === active.sectionId);

  return (
    <div className="datil-app">
      <Navbar modules={modules} active={active} onSelect={open} badges={{ avisos: unread }} />
      <div className="datil-content-area">
        <main className="datil-content">
          {ActiveModule ? (
            <Suspense fallback={<p role="status">Cargando...</p>}>
              <ActiveModule section={activeSection} onUnreadChange={setUnread} goTo={(sectionId) => open(activeModule, sectionId)} />
            </Suspense>
          ) : (
            <p>No tienes módulos habilitados todavía. Pide a tu administrador que te asigne los permisos que necesitas.</p>
          )}
        </main>
      </div>
    </div>
  );
}
