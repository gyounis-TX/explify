import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { HashRouter } from "react-router-dom";
import App from "./App";
import { ErrorBoundary } from "./components/shared/ErrorBoundary";
import { ToastProvider } from "./components/shared/Toast";
import { getSupabase } from "./services/supabase";
import "./styles/global.css";

// Supabase email confirmation redirects put the token in the hash fragment.
// In the browser (outside Tauri), show a confirmation message instead of
// loading the full app, since the backend sidecar isn't available.
const hash = window.location.hash;
const isAuthRedirect = hash.includes("access_token=") && hash.includes("type=");

if (isAuthRedirect) {
  // Let Supabase consume the token to complete email verification
  const supabase = getSupabase();
  if (supabase) {
    const params = new URLSearchParams(hash.substring(1));
    const accessToken = params.get("access_token");
    const refreshToken = params.get("refresh_token");
    if (accessToken && refreshToken) {
      supabase.auth.setSession({ access_token: accessToken, refresh_token: refreshToken });
    }
  }

  // Show a simple confirmation page
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
        <div style="font-size: 48px; margin-bottom: 16px;">&#10003;</div>
        <h1 style="font-size: 1.5rem; color: #1e293b; margin: 0 0 12px;">Email Confirmed</h1>
        <p style="color: #64748b; font-size: 1rem; line-height: 1.5; margin: 0;">
          Your email has been verified. You can close this tab and sign in from the Explify app.
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
