import { Routes, Route } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { ImportScreen } from "./components/import/ImportScreen";
import { TemplatesScreen } from "./components/templates/TemplatesScreen";
import { SettingsScreen } from "./components/settings/SettingsScreen";
import { AIModelScreen } from "./components/ai-model/AIModelScreen";
import { ProcessingScreen } from "./components/processing/ProcessingScreen";
import { ResultsScreen } from "./components/results/ResultsScreen";
import { HistoryScreen } from "./components/history/HistoryScreen";
import { LettersScreen } from "./components/letters/LettersScreen";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<ImportScreen />} />
        <Route path="/history" element={<HistoryScreen />} />
        <Route path="/letters" element={<LettersScreen />} />
        <Route path="/templates" element={<TemplatesScreen />} />
        <Route path="/settings" element={<SettingsScreen />} />
        <Route path="/ai-model" element={<AIModelScreen />} />
        <Route path="/processing" element={<ProcessingScreen />} />
        <Route path="/results" element={<ResultsScreen />} />
      </Route>
    </Routes>
  );
}

export default App;
