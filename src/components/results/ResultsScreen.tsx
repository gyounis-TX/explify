import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type {
  ExplainResponse,
  MeasurementExplanation,
  FindingExplanation,
  ParsedMeasurement,
} from "../../types/sidecar";
import { sidecarApi } from "../../services/sidecarApi";
import { GlossaryTooltip } from "./GlossaryTooltip";
import "./ResultsScreen.css";

const SEVERITY_LABELS: Record<string, string> = {
  normal: "Normal",
  mildly_abnormal: "Mildly Abnormal",
  moderately_abnormal: "Moderately Abnormal",
  severely_abnormal: "Severely Abnormal",
  undetermined: "Undetermined",
};

const SEVERITY_ICONS: Record<string, string> = {
  normal: "\u2713",
  mildly_abnormal: "\u26A0",
  moderately_abnormal: "\u25B2",
  severely_abnormal: "\u2716",
  undetermined: "\u2014",
};

const FINDING_SEVERITY_COLORS: Record<string, string> = {
  normal: "var(--color-accent-600)",
  mild: "#d97706",
  moderate: "#ea580c",
  severe: "#dc2626",
  informational: "var(--color-primary-600)",
};

const FINDING_SEVERITY_ICONS: Record<string, string> = {
  normal: "\u2713",
  mild: "\u26A0",
  moderate: "\u25B2",
  severe: "\u2716",
  informational: "\u24D8",
};

export function ResultsScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const explainResponse = (
    location.state as { explainResponse?: ExplainResponse }
  )?.explainResponse;

  const [glossary, setGlossary] = useState<Record<string, string>>({});
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    if (!explainResponse) return;
    const testType = explainResponse.parsed_report.test_type;
    sidecarApi
      .getGlossary(testType)
      .then((res) => setGlossary(res.glossary))
      .catch(() => {});
  }, [explainResponse]);

  if (!explainResponse) {
    return (
      <div className="results-screen">
        <h2 className="results-title">No Results</h2>
        <p className="results-empty">
          No analysis results found. Please import and process a report
          first.
        </p>
        <button
          className="results-back-btn"
          onClick={() => navigate("/")}
        >
          Back to Import
        </button>
      </div>
    );
  }

  const { explanation, parsed_report } = explainResponse;

  const measurementMap = new Map<string, ParsedMeasurement>();
  if (parsed_report.measurements) {
    for (const m of parsed_report.measurements) {
      measurementMap.set(m.abbreviation, m);
    }
  }

  const handleExportPdf = async () => {
    setIsExporting(true);
    try {
      const blob = await sidecarApi.exportPdf(explainResponse);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "verba-report.pdf";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // PDF export failed silently
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="results-screen">
      <header className="results-header">
        <h2 className="results-title">Report Explanation</h2>
        <span className="results-test-type">
          {parsed_report.test_type_display}
        </span>
      </header>

      {/* Export Toolbar */}
      <div className="export-toolbar">
        <button
          className="export-btn"
          onClick={handleExportPdf}
          disabled={isExporting}
        >
          {isExporting ? "Exporting\u2026" : "Export PDF"}
        </button>
        <button className="export-btn" onClick={() => window.print()}>
          Print
        </button>
      </div>

      {/* Overall Summary */}
      <section className="results-section">
        <h3 className="section-heading">Summary</h3>
        <p className="summary-text">
          <GlossaryTooltip
            text={explanation.overall_summary}
            glossary={glossary}
          />
        </p>
      </section>

      {/* Key Findings */}
      {explanation.key_findings.length > 0 && (
        <details open className="results-section results-collapsible">
          <summary className="section-heading">
            Key Findings
            <span className="section-count">
              {explanation.key_findings.length}
            </span>
          </summary>
          <div className="section-body">
            <div className="findings-list">
              {explanation.key_findings.map(
                (f: FindingExplanation, i: number) => (
                  <div key={i} className="finding-card">
                    <div className="finding-header">
                      <span
                        className={`finding-severity finding-severity--${f.severity}`}
                        aria-label={`Severity: ${f.severity}`}
                        style={{
                          backgroundColor:
                            FINDING_SEVERITY_COLORS[f.severity] ||
                            "var(--color-gray-400)",
                        }}
                      >
                        {FINDING_SEVERITY_ICONS[f.severity] || "\u2014"}
                      </span>
                      <span className="finding-title">
                        <GlossaryTooltip
                          text={f.finding}
                          glossary={glossary}
                        />
                      </span>
                    </div>
                    <p className="finding-explanation">
                      <GlossaryTooltip
                        text={f.explanation}
                        glossary={glossary}
                      />
                    </p>
                  </div>
                ),
              )}
            </div>
          </div>
        </details>
      )}

      {/* Measurements Table */}
      {explanation.measurements.length > 0 && (
        <details open className="results-section results-collapsible">
          <summary className="section-heading">
            Measurements
            <span className="section-count">
              {explanation.measurements.length}
            </span>
          </summary>
          <div className="section-body">
            <div className="measurements-table-container">
              <table
                className="measurements-table"
                aria-label="Measurement results"
              >
                <thead>
                  <tr>
                    <th scope="col">Measurement</th>
                    <th scope="col">Value</th>
                    <th scope="col">Normal Range</th>
                    <th scope="col">Status</th>
                    <th scope="col">Explanation</th>
                  </tr>
                </thead>
                <tbody>
                  {explanation.measurements.map(
                    (m: MeasurementExplanation, i: number) => {
                      const parsed = measurementMap.get(m.abbreviation);
                      return (
                        <tr
                          key={i}
                          className={`measurement-row measurement-row--${m.status}`}
                        >
                          <td className="measurement-name">
                            <GlossaryTooltip
                              text={m.abbreviation}
                              glossary={glossary}
                            />
                          </td>
                          <td className="measurement-value">
                            {m.value} {m.unit}
                          </td>
                          <td className="measurement-range">
                            {parsed?.reference_range || "--"}
                          </td>
                          <td className="measurement-status">
                            <span
                              className={`status-badge status-badge--${m.status}`}
                              aria-label={`Status: ${SEVERITY_LABELS[m.status] || m.status}`}
                            >
                              <span className="status-badge__icon">
                                {SEVERITY_ICONS[m.status] || ""}
                              </span>{" "}
                              {SEVERITY_LABELS[m.status] || m.status}
                            </span>
                          </td>
                          <td className="measurement-explanation">
                            <GlossaryTooltip
                              text={m.plain_language}
                              glossary={glossary}
                            />
                          </td>
                        </tr>
                      );
                    },
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </details>
      )}

      {/* Questions for Doctor */}
      {explanation.questions_for_doctor.length > 0 && (
        <details open className="results-section results-collapsible">
          <summary className="section-heading">
            Questions to Ask Your Doctor
            <span className="section-count">
              {explanation.questions_for_doctor.length}
            </span>
          </summary>
          <div className="section-body">
            <ul className="questions-list">
              {explanation.questions_for_doctor.map(
                (q: string, i: number) => (
                  <li key={i} className="question-item">
                    {q}
                  </li>
                ),
              )}
            </ul>
          </div>
        </details>
      )}

      {/* Disclaimer */}
      <section className="results-disclaimer">
        <p>{explanation.disclaimer}</p>
      </section>

      {/* Metadata */}
      <footer className="results-footer">
        <span className="results-meta">
          Model: {explainResponse.model_used} | Tokens:{" "}
          {explainResponse.input_tokens} in /{" "}
          {explainResponse.output_tokens} out
        </span>
        {explainResponse.validation_warnings.length > 0 && (
          <details className="validation-warnings">
            <summary>
              Validation Warnings (
              {explainResponse.validation_warnings.length})
            </summary>
            <ul>
              {explainResponse.validation_warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </details>
        )}
      </footer>

      <button
        className="results-back-btn"
        onClick={() => navigate("/")}
      >
        Analyze Another Report
      </button>
    </div>
  );
}
