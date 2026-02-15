import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import { ErrorBoundary } from "./components/shared/ErrorBoundary";
import { ToastProvider } from "./components/shared/Toast";
import { initSentry } from "./services/sentry";
import "./styles/global.css";

// Initialize Sentry as early as possible
initSentry();

// Detect whether we're running inside Tauri or in a plain browser.
const isTauri = "__TAURI__" in window || "__TAURI_INTERNALS__" in window;

if (!isTauri && !import.meta.env.VITE_API_URL && !window.location.hostname.match(/^(localhost|127\.0\.0\.1)$/)) {
  // Opened in a browser without Tauri and without a configured API URL.
  // Show a message instead of a blank page.
  const root = document.getElementById("root")!;
  root.innerHTML = `
    <div style="
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      background: #f8fafc;
      font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    ">
      <div style="
        text-align: center;
        max-width: 420px;
        padding: 48px 32px;
        background: white;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
      ">
        <h1 style="font-size: 1.5rem; color: #1e293b; margin: 0 0 12px;">Explify</h1>
        <p style="color: #64748b; font-size: 1rem; line-height: 1.5; margin: 0;">
          Please open the Explify desktop app to continue.
        </p>
      </div>
    </div>
  `;
} else {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <ErrorBoundary>
        <ToastProvider>
          <HashRouter>
            <App />
          </HashRouter>
        </ToastProvider>
      </ErrorBoundary>
    </StrictMode>
  );
}
