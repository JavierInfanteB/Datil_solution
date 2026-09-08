import { useEffect, useState } from "react";
import apiClient from "../api/client";
import { getAvailableModules } from "../modules/moduleRegistry";
import Navbar from "../components/Navbar";

export default function DashboardPage() {
  const [modules, setModules] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiClient
      .get("/api/permissions/me")
      .then(({ data }) => {
        const available = getAvailableModules(data.modules);
        setModules(available);
        setActiveId(available[0]?.id ?? null);
      })
      .catch(() => setError("No se pudieron cargar tus permisos."));
  }, []);

  if (error) return <p className="datil-error">{error}</p>;
  if (!modules) return <p>Cargando modulos...</p>;

  const ActiveModule = modules.find((m) => m.id === activeId)?.Component;

  return (
    <div className="datil-app">
      <Navbar modules={modules} activeId={activeId} onSelect={setActiveId} />
      <div className="datil-content-area">
        <main className="datil-content">
          {ActiveModule ? <ActiveModule /> : <p>No tienes modulos habilitados todavia.</p>}
        </main>
      </div>
    </div>
  );
}
