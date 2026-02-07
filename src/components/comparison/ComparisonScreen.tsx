import { useEffect, useState, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type {
  HistoryDetailResponse,
  MeasurementExplanation,
  FindingExplanation,
} from "../../types/sidecar";
import { sidecarApi } from "../../services/sidecarApi";
import { useToast } from "../shared/Toast";
import "./ComparisonScreen.css";

// ---------------------------------------------------------------------------
// Types for computed comparison data
// ---------------------------------------------------------------------------

type MeasurementTrend = "increased" | "decreased" | "stable" | "new" | "removed";

interface MeasurementComparison {
  abbreviation: string;
  newer: MeasurementExplanation | null;
  older: MeasurementExplanation | null;
  trend: MeasurementTrend;
  deltaPercent: number | null;
}

type FindingChangeType = "new" | "resolved" | "unchanged";

interface FindingChange {
  finding: string;
  changeType: FindingChangeType;
  newerDetail: FindingExplanation | null;
  olderDetail: FindingExplanation | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function computeMeasurementComparisons(
  newer: MeasurementExplanation[],
  older: MeasurementExplanation[],
): MeasurementComparison[] {
  const olderMap = new Map<string, MeasurementExplanation>();
  for (const m of older) {
    olderMap.set(m.abbreviation.toLowerCase(), m);
  }

  const seen = new Set<string>();
  const results: MeasurementComparison[] = [];

  // Walk newer measurements
  for (const nm of newer) {
    const key = nm.abbreviation.toLowerCase();
    seen.add(key);
    const om = olderMap.get(key) ?? null;

    if (!om) {
      results.push({
        abbreviation: nm.abbreviation,
        newer: nm,
        older: null,
        trend: "new",
        deltaPercent: null,
      });
      continue;
    }

    const nv = nm.value;
    const ov = om.value;

    if (typeof nv === "number" && typeof ov === "number" && ov !== 0) {
      const pct = ((nv - ov) / Math.abs(ov)) * 100;
      let trend: MeasurementTrend;
      if (Math.abs(pct) <= 5) {
        trend = "stable";
      } else if (pct > 0) {
        trend = "increased";
      } else {
        trend = "decreased";
      }
      results.push({
        abbreviation: nm.abbreviation,
        newer: nm,
        older: om,
        trend,
        deltaPercent: Math.round(pct * 10) / 10,
      });
    } else {
      results.push({
        abbreviation: nm.abbreviation,
        newer: nm,
        older: om,
        trend: "stable",
        deltaPercent: null,
      });
    }
  }

  // Measurements only in older
  for (const om of older) {
    const key = om.abbreviation.toLowerCase();
    if (!seen.has(key)) {
      results.push({
        abbreviation: om.abbreviation,
        newer: null,
        older: om,
        trend: "removed",
        deltaPercent: null,
      });
    }
  }

  return results;
}

function computeFindingChanges(
  newer: FindingExplanation[],
  older: FindingExplanation[],
): FindingChange[] {
  const olderMap = new Map<string, FindingExplanation>();
  for (const f of older) {
    olderMap.set(f.finding.toLowerCase(), f);
  }

  const seen = new Set<string>();
  const changes: FindingChange[] = [];

  for (const nf of newer) {
    const key = nf.finding.toLowerCase();
    seen.add(key);
    const of_ = olderMap.get(key) ?? null;

    if (!of_) {
      changes.push({ finding: nf.finding, changeType: "new", newerDetail: nf, olderDetail: null });
    } else {
      changes.push({ finding: nf.finding, changeType: "unchanged", newerDetail: nf, olderDetail: of_ });
    }
  }

  for (const of_ of older) {
    const key = of_.finding.toLowerCase();
    if (!seen.has(key)) {
      changes.push({ finding: of_.finding, changeType: "resolved", newerDetail: null, olderDetail: of_ });
    }
  }

  return changes;
}

function trendArrow(trend: MeasurementTrend): string {
  switch (trend) {
    case "increased":
      return "\u2191";
    case "decreased":
      return "\u2193";
    case "stable":
      return "\u2192";
    case "new":
      return "+";
    case "removed":
      return "\u2013";
  }
}

function trendLabel(trend: MeasurementTrend): string {
  switch (trend) {
    case "increased":
      return "Increased";
    case "decreased":
      return "Decreased";
    case "stable":
      return "Stable";
    case "new":
      return "New";
    case "removed":
      return "No longer reported";
  }
}

function changeIcon(changeType: FindingChangeType): string {
  switch (changeType) {
    case "new":
      return "+";
    case "resolved":
      return "\u2013";
    case "unchanged":
      return "=";
  }
}

function changeLabel(changeType: FindingChangeType): string {
  switch (changeType) {
    case "new":
      return "NEW";
    case "resolved":
      return "RESOLVED";
    case "unchanged":
      return "UNCHANGED";
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ComparisonScreen() {
  const location = useLocation();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const locationState = location.state as {
    historyIds?: [number, number];
  } | null;

  const historyIds = locationState?.historyIds ?? null;

  // Data state
  const [newerDetail, setNewerDetail] = useState<HistoryDetailResponse | null>(null);
  const [olderDetail, setOlderDetail] = useState<HistoryDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // LLM trend summary
  const [trendSummary, setTrendSummary] = useState<string | null>(null);
  const [trendLoading, setTrendLoading] = useState(false);

  // Computed comparisons
  const [measurementComparisons, setMeasurementComparisons] = useState<MeasurementComparison[]>([]);
  const [findingChanges, setFindingChanges] = useState<FindingChange[]>([]);

  // ---------------------------------------------------------------------------
  // Fetch both history details on mount
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!historyIds || historyIds.length !== 2) {
      setError("Two history IDs are required for comparison.");
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function fetchDetails() {
      try {
        const [detailA, detailB] = await Promise.all([
          sidecarApi.getHistoryDetail(historyIds![0]),
          sidecarApi.getHistoryDetail(historyIds![1]),
        ]);

        if (cancelled) return;

        // Determine which is newer by created_at
        const dateA = new Date(detailA.created_at).getTime();
        const dateB = new Date(detailB.created_at).getTime();

        let newer: HistoryDetailResponse;
        let older: HistoryDetailResponse;
        if (dateA >= dateB) {
          newer = detailA;
          older = detailB;
        } else {
          newer = detailB;
          older = detailA;
        }

        setNewerDetail(newer);
        setOlderDetail(older);

        // Compute client-side comparisons
        const newerExpl = newer.full_response.explanation;
        const olderExpl = older.full_response.explanation;

        setMeasurementComparisons(
          computeMeasurementComparisons(newerExpl.measurements, olderExpl.measurements),
        );
        setFindingChanges(
          computeFindingChanges(newerExpl.key_findings, olderExpl.key_findings),
        );

        setLoading(false);

        // Fetch LLM trend summary
        fetchTrendSummary(newer, older);
      } catch (err) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : "Failed to load report details.";
        setError(msg);
        setLoading(false);
        showToast("error", msg);
      }
    }

    async function fetchTrendSummary(
      newer: HistoryDetailResponse,
      older: HistoryDetailResponse,
    ) {
      setTrendLoading(true);
      try {
        const result = await sidecarApi.compareReports(
          newer.full_response,
          older.full_response,
          newer.created_at,
          older.created_at,
        );
        if (!cancelled) {
          setTrendSummary(result.trend_summary);
        }
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "Failed to generate trend summary.";
          showToast("error", msg);
          setTrendSummary("Unable to generate trend summary. Please try again later.");
        }
      } finally {
        if (!cancelled) {
          setTrendLoading(false);
        }
      }
    }

    fetchDetails();

    return () => {
      cancelled = true;
    };
  }, [historyIds, showToast]);

  // ---------------------------------------------------------------------------
  // Copy trend summary
  // ---------------------------------------------------------------------------
  const handleCopyTrend = useCallback(async () => {
    if (!trendSummary) return;
    try {
      await navigator.clipboard.writeText(trendSummary);
      showToast("success", "Trend summary copied to clipboard.");
    } catch {
      showToast("error", "Failed to copy to clipboard.");
    }
  }, [trendSummary, showToast]);

  // ---------------------------------------------------------------------------
  // Error / loading states
  // ---------------------------------------------------------------------------
  if (!historyIds || historyIds.length !== 2) {
    return (
      <div className="comparison-screen">
        <h2 className="comparison-title">Report Comparison</h2>
        <p className="comparison-empty">
          No reports selected for comparison. Please select two reports from the history screen.
        </p>
        <div className="comparison-actions">
          <button className="comparison-back-btn" onClick={() => navigate("/history")}>
            Back to History
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="comparison-screen">
        <h2 className="comparison-title">Report Comparison</h2>
        <div className="comparison-loading">
          <div className="comparison-spinner" />
          <span>Loading report details...</span>
        </div>
      </div>
    );
  }

  if (error || !newerDetail || !olderDetail) {
    return (
      <div className="comparison-screen">
        <h2 className="comparison-title">Report Comparison</h2>
        <div className="comparison-error">
          <p>{error ?? "An unexpected error occurred."}</p>
        </div>
        <div className="comparison-actions">
          <button className="comparison-back-btn" onClick={() => navigate("/history")}>
            Back to History
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  const newerDate = formatDate(newerDetail.created_at);
  const olderDate = formatDate(olderDetail.created_at);
  const testTypeDisplay = newerDetail.test_type_display || olderDetail.test_type_display || "Report";

  return (
    <div className="comparison-screen">
      <header className="comparison-header">
        <h2 className="comparison-title">Report Comparison &mdash; {testTypeDisplay}</h2>
        <p className="comparison-date-range">{newerDate} vs {olderDate}</p>
      </header>

      {/* Trend Summary (LLM) */}
      <section className="comparison-trend">
        <h3 className="comparison-section-heading">Trend Summary</h3>
        {trendLoading ? (
          <div className="comparison-trend-loading">
            <div className="comparison-spinner" />
            <span>Generating trend analysis...</span>
          </div>
        ) : (
          <p className="comparison-trend-text">{trendSummary}</p>
        )}
        <button
          className="comparison-copy-btn"
          onClick={handleCopyTrend}
          disabled={trendLoading || !trendSummary}
        >
          Copy Trend Summary
        </button>
      </section>

      {/* Measurements Table */}
      <section className="comparison-measurements">
        <h3 className="comparison-section-heading">Measurements</h3>
        {measurementComparisons.length === 0 ? (
          <p className="comparison-empty-section">No measurements to compare.</p>
        ) : (
          <div className="comparison-table-container">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th>Measurement</th>
                  <th>{newerDate}</th>
                  <th>{olderDate}</th>
                  <th>Trend</th>
                </tr>
              </thead>
              <tbody>
                {measurementComparisons.map((mc) => (
                  <tr key={mc.abbreviation} className={`comparison-row comparison-row--${mc.trend}`}>
                    <td className="comparison-cell-measurement">
                      <span className="comparison-abbr">{mc.abbreviation}</span>
                    </td>
                    <td className="comparison-cell-value">
                      {mc.newer
                        ? `${mc.newer.value} ${mc.newer.unit}`
                        : "\u2014"}
                    </td>
                    <td className="comparison-cell-value">
                      {mc.older
                        ? `${mc.older.value} ${mc.older.unit}`
                        : "\u2014"}
                    </td>
                    <td className="comparison-cell-trend">
                      <span className={`comparison-trend-badge comparison-trend-badge--${mc.trend}`}>
                        <span className="comparison-trend-arrow">{trendArrow(mc.trend)}</span>
                        {" "}
                        {trendLabel(mc.trend)}
                        {mc.deltaPercent !== null && mc.trend !== "stable" && (
                          <span className="comparison-trend-delta">
                            {" "}({mc.deltaPercent > 0 ? "+" : ""}{mc.deltaPercent}%)
                          </span>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Key Findings Changes */}
      <section className="comparison-findings">
        <h3 className="comparison-section-heading">Key Findings Changes</h3>
        {findingChanges.length === 0 ? (
          <p className="comparison-empty-section">No findings to compare.</p>
        ) : (
          <div className="comparison-findings-list">
            {findingChanges.map((fc, idx) => (
              <div key={idx} className={`comparison-finding-card comparison-finding-card--${fc.changeType}`}>
                <div className="comparison-finding-header">
                  <span className={`comparison-change-badge comparison-change-badge--${fc.changeType}`}>
                    <span className="comparison-change-icon">{changeIcon(fc.changeType)}</span>
                    {" "}
                    {changeLabel(fc.changeType)}
                  </span>
                  <span className="comparison-finding-title">{fc.finding}</span>
                </div>
                {(fc.newerDetail || fc.olderDetail) && (
                  <p className="comparison-finding-explanation">
                    {fc.newerDetail?.explanation ?? fc.olderDetail?.explanation ?? ""}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="comparison-actions">
        <button className="comparison-back-btn" onClick={() => navigate("/history")}>
          Back to History
        </button>
      </div>
    </div>
  );
}
