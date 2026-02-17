import type { ExplainResponse } from "../../types/sidecar";
import "./ResultsScreen.css";

interface BatchComparisonTableProps {
  batchResponses: ExplainResponse[];
  batchLabels?: string[];
}

export function BatchComparisonTable({ batchResponses, batchLabels }: BatchComparisonTableProps) {
  // Collect all unique measurement abbreviations across responses
  const allAbbreviations = new Set<string>();
  const responseData = batchResponses.map((resp, idx) => {
    const measurements = resp.explanation?.measurements ?? [];
    const byAbbr = new Map<string, { value: string; unit: string; status: string }>();
    for (const m of measurements) {
      allAbbreviations.add(m.abbreviation);
      byAbbr.set(m.abbreviation, {
        value: String(m.value ?? ""),
        unit: m.unit ?? "",
        status: m.status ?? "undetermined",
      });
    }
    return { label: batchLabels?.[idx] ?? `Report ${idx + 1}`, byAbbr };
  });

  const abbreviations = Array.from(allAbbreviations);
  if (abbreviations.length === 0) {
    return <p className="results-empty">No comparable measurements found across reports.</p>;
  }

  function getChangeIndicator(values: (string | undefined)[]): string {
    const nums = values.map((v) => (v ? parseFloat(v) : NaN)).filter((n) => !isNaN(n));
    if (nums.length < 2) return "";
    const diff = nums[nums.length - 1] - nums[0];
    if (diff > 0) return "\u2191";
    if (diff < 0) return "\u2193";
    return "\u2194";
  }

  return (
    <div className="batch-comparison-table">
      <div className="measurements-table-container">
        <table className="measurements-table">
          <thead>
            <tr>
              <th>Measurement</th>
              {responseData.map((r, i) => (
                <th key={i}>{r.label}</th>
              ))}
              <th>Change</th>
            </tr>
          </thead>
          <tbody>
            {abbreviations.map((abbr) => {
              const values = responseData.map((r) => r.byAbbr.get(abbr));
              const changeIndicator = getChangeIndicator(values.map((v) => v?.value));
              return (
                <tr key={abbr}>
                  <td><strong>{abbr}</strong></td>
                  {values.map((v, i) => (
                    <td key={i} className={v ? `measurement-cell--${v.status}` : ""}>
                      {v ? `${v.value} ${v.unit}` : "\u2014"}
                    </td>
                  ))}
                  <td className="batch-comparison-change">{changeIndicator}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
