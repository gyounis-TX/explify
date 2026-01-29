import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { useSidecar } from "../../hooks/useSidecar";
import "./AppShell.css";

export function AppShell() {
  const { isReady, error } = useSidecar();

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-content">
        {error ? (
          <div className="sidecar-error">
            <h2>Connection Error</h2>
            <p>{error}</p>
          </div>
        ) : !isReady ? (
          <div className="sidecar-loading">
            <p>Starting backend services...</p>
          </div>
        ) : (
          <Outlet />
        )}
      </main>
    </div>
  );
}
