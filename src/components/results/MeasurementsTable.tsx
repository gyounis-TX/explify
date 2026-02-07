import type { MeasurementExplanation, ParsedMeasurement } from "../../types/sidecar";
import { GlossaryTooltip } from "./GlossaryTooltip";

const SEVERITY_LABELS: Record<string, string> = {
  normal: "Normal",
  mildly_abnormal: "Mildly Abnormal",
  moderately_abnormal: "Moderately Abnormal",
  severely_abnormal: "Severely Abnormal",
  critical: "CRITICAL",
  undetermined: "Undetermined",
};

const SEVERITY_ICONS: Record<string, string> = {
  normal: "\u2713",
  mildly_abnormal: "\u26A0",
  moderately_abnormal: "\u25B2",
  severely_abnormal: "\u2716",
  critical: "\u26A0\u26A0",
  undetermined: "\u2014",
};

interface MeasurementsTableProps {
  measurements: MeasurementExplanation[];
  measurementMap: Map<string, ParsedMeasurement>;
  glossary: Record<string, string>;
}

export function MeasurementsTable({
  measurements,
  measurementMap,
  glossary,
}: MeasurementsTableProps) {
  if (measurements.length === 0) return null;

  return (
    <details open className="results-section results-collapsible">
      <summary className="section-heading">
        Measurements
        <span className="section-count">{measurements.length}</span>
      </summary>
      <div className="section-body">
        <div className="measurements-legend">
          <span className="legend-item"><span className="legend-swatch legend-swatch--normal" />{SEVERITY_ICONS.normal} Normal</span>
          <span className="legend-item"><span className="legend-swatch legend-swatch--mildly_abnormal" />{SEVERITY_ICONS.mildly_abnormal} Mildly Abnormal</span>
          <span className="legend-item"><span className="legend-swatch legend-swatch--moderately_abnormal" />{SEVERITY_ICONS.moderately_abnormal} Moderately Abnormal</span>
          <span className="legend-item"><span className="legend-swatch legend-swatch--severely_abnormal" />{SEVERITY_ICONS.severely_abnormal} Severely Abnormal</span>
          <span className="legend-item"><span className="legend-swatch legend-swatch--undetermined" />{SEVERITY_ICONS.undetermined} Undetermined</span>
        </div>
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
              {measurements.map((m, i) => {
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
              })}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  );
}
