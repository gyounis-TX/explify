import { Routes, Route } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ImportScreen } from "./components/import/ImportScreen";
import { TemplatesScreen } from "./components/templates/TemplatesScreen";
import { SettingsScreen } from "./components/settings/SettingsScreen";
import { ProcessingScreen } from "./components/processing/ProcessingScreen";
import { ResultsScreen } from "./components/results/ResultsScreen";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<ImportScreen />} />
        <Route path="/templates" element={<TemplatesScreen />} />
        <Route path="/settings" element={<SettingsScreen />} />
        <Route path="/processing" element={<ProcessingScreen />} />
        <Route path="/results" element={<ResultsScreen />} />
      </Route>
    </Routes>
  );
}

export default App;
