import { useState, useEffect } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ImportScreen } from "./components/import/ImportScreen";
import { TemplatesScreen } from "./components/templates/TemplatesScreen";
import { SettingsScreen } from "./components/settings/SettingsScreen";
import { AdminScreen } from "./components/admin/AdminScreen";
import { ProcessingScreen } from "./components/processing/ProcessingScreen";
import { ResultsScreen } from "./components/results/ResultsScreen";
import { HistoryScreen } from "./components/history/HistoryScreen";
import { LettersScreen } from "./components/letters/LettersScreen";
import { TeachingPointsScreen } from "./components/teaching-points/TeachingPointsScreen";
import { ComparisonScreen } from "./components/comparison/ComparisonScreen";
import { AuthScreen } from "./components/auth/AuthScreen";
import { LegalPage } from "./components/legal/LegalPage";
import { LandingPage } from "./components/landing/LandingPage";
import { IS_TAURI } from "./services/platform";
import { getSession } from "./services/supabase";

function AuthRoute() {
  const navigate = useNavigate();
  return <AuthScreen onAuthSuccess={() => navigate(IS_TAURI ? "/" : "/import")} />;
}

/** Web mode root: show landing page for unauthenticated, redirect to /import for authenticated. */
function WebRoot() {
  const [checked, setChecked] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    getSession().then((s) => {
      setAuthed(!!s);
      setChecked(true);
    }).catch(() => setChecked(true));
  }, []);

  if (!checked) return null;
  if (authed) return <Navigate to="/import" replace />;
  return <LandingPage />;
}

function App() {
  return (
    <Routes>
      {/* Public pages — no auth or sidebar */}
      <Route path="/terms" element={<LegalPage title="Terms of Service" markdownPath="/legal/terms.md" />} />
      <Route path="/privacy" element={<LegalPage title="Privacy Policy" markdownPath="/legal/privacy.md" />} />

      {/* Web mode: landing page at / for unauthenticated users */}
      {!IS_TAURI && <Route path="/" element={<WebRoot />} />}

      <Route element={<AppShell />}>
        {/* Tauri: / is Import. Web: /import is Import. */}
        {IS_TAURI ? (
          <Route path="/" element={<ImportScreen />} />
        ) : (
          <Route path="/import" element={<ImportScreen />} />
        )}
        <Route path="/history" element={<HistoryScreen />} />
        <Route path="/letters" element={<LettersScreen />} />
        <Route path="/teaching-points" element={<TeachingPointsScreen />} />
        <Route path="/templates" element={<TemplatesScreen />} />
        <Route path="/settings" element={<SettingsScreen />} />
        <Route path="/admin" element={<AdminScreen />} />
        <Route path="/processing" element={<ProcessingScreen />} />
        <Route path="/results" element={<ResultsScreen />} />
        <Route path="/comparison" element={<ComparisonScreen />} />
        <Route path="/auth" element={<AuthRoute />} />
      </Route>
    </Routes>
  );
}

export default App;
