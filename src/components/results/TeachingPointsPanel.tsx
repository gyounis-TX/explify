import type { TeachingPoint, SharedTeachingPoint } from "../../types/sidecar";
import { sidecarApi } from "../../services/sidecarApi";
import { queueUpsertAfterMutation } from "../../services/syncEngine";

interface TeachingPointsPanelProps {
  teachingPoints: TeachingPoint[];
  setTeachingPoints: React.Dispatch<React.SetStateAction<TeachingPoint[]>>;
  sharedTeachingPoints: SharedTeachingPoint[];
  newTeachingPoint: string;
  setNewTeachingPoint: (value: string) => void;
  effectiveTestType: string;
  effectiveTestTypeDisplay: string;
  testTypeOverride: string | null;
  setTestTypeOverride: (value: string | null) => void;
  showToast: (type: "success" | "error" | "info", message: string) => void;
  showUndoToast: (message: string, onUndo: () => void, duration?: number) => void;
  letterMode?: boolean;
}

export function TeachingPointsPanel({
  teachingPoints,
  setTeachingPoints,
  sharedTeachingPoints,
  newTeachingPoint,
  setNewTeachingPoint,
  effectiveTestType,
  effectiveTestTypeDisplay,
  testTypeOverride,
  setTestTypeOverride,
  showToast,
  showUndoToast,
  letterMode,
}: TeachingPointsPanelProps) {
  const totalCount = teachingPoints.length + sharedTeachingPoints.length;

  const handleSaveForType = async () => {
    if (!newTeachingPoint.trim()) return;
    try {
      const tp = await sidecarApi.createTeachingPoint({
        text: newTeachingPoint.trim(),
        test_type: effectiveTestType,
      });
      setTeachingPoints((prev) => [tp, ...prev]);
      setNewTeachingPoint("");
      queueUpsertAfterMutation("teaching_points", tp.id).catch(() => {});
    } catch {
      showToast("error", "Failed to save teaching point.");
    }
  };

  const handleSaveForAll = async () => {
    if (!newTeachingPoint.trim()) return;
    try {
      const tp = await sidecarApi.createTeachingPoint({
        text: newTeachingPoint.trim(),
      });
      setTeachingPoints((prev) => [tp, ...prev]);
      setNewTeachingPoint("");
      queueUpsertAfterMutation("teaching_points", tp.id).catch(() => {});
    } catch {
      showToast("error", "Failed to save teaching point.");
    }
  };

  const handleDelete = (id: number) => {
    const point = teachingPoints.find((p) => p.id === id);
    if (!point) return;

    // Optimistic removal
    setTeachingPoints((prev) => prev.filter((p) => p.id !== id));

    // Schedule actual deletion after undo window
    const timer = setTimeout(async () => {
      try {
        await sidecarApi.deleteTeachingPoint(id);
      } catch {
        setTeachingPoints((prev) => [point, ...prev]);
        showToast("error", "Failed to delete teaching point.");
      }
    }, 5200);

    showUndoToast("Teaching point deleted.", () => {
      clearTimeout(timer);
      setTeachingPoints((prev) => [point, ...prev]);
      showToast("success", "Teaching point restored.");
    });
  };

  return (
    <details className="teaching-points-panel teaching-points-collapsible">
      <summary className="teaching-points-header">
        <h3>Teaching Points</h3>
        {totalCount > 0 && (
          <span className="teaching-points-count">{totalCount}</span>
        )}
      </summary>
      <div className="teaching-points-body">
        {!letterMode && testTypeOverride !== undefined && (
          <div className="teaching-points-type-row">
            <label className="teaching-points-type-label">Report type:</label>
            <input
              type="text"
              className="teaching-points-type-input"
              value={testTypeOverride ?? effectiveTestTypeDisplay}
              onChange={(e) => setTestTypeOverride(e.target.value)}
              placeholder="e.g. Calcium Score CT"
            />
          </div>
        )}
        <p className="teaching-points-desc">
          {letterMode
            ? "Add personalized instructions that customize how AI generates letters. These points can be stylistic or clinical. Explify will remember and apply these to all future outputs."
            : "Add personalized instructions that customize how AI interprets and explains results. These points can be stylistic or clinical. Explify will remember and apply these to all future explanations."}
        </p>
        <div className="teaching-point-input-row">
          <textarea
            className="teaching-point-input"
            placeholder={letterMode
              ? "e.g. Always use a warm, conversational tone"
              : "e.g. Always mention diastolic dysfunction grading"}
            value={newTeachingPoint}
            onChange={(e) => setNewTeachingPoint(e.target.value)}
            rows={3}
          />
          <div className="teaching-point-save-row">
            {!letterMode && (
              <button
                className="teaching-point-save-btn"
                disabled={!newTeachingPoint.trim()}
                onClick={handleSaveForType}
              >
                Save for {effectiveTestTypeDisplay}
              </button>
            )}
            <button
              className={letterMode ? "teaching-point-save-btn" : "teaching-point-save-btn teaching-point-save-btn--all"}
              disabled={!newTeachingPoint.trim()}
              onClick={handleSaveForAll}
            >
              Save for all types
            </button>
          </div>
        </div>
        {teachingPoints.length > 0 && (
          <div className="own-teaching-points">
            <span className="own-teaching-points-label">Your teaching points</span>
            {teachingPoints.map((tp) => (
              <div key={tp.id} className="own-teaching-point-card">
                <p className="own-teaching-point-text">{tp.text}</p>
                <div className="own-teaching-point-meta">
                  {tp.test_type ? (
                    <span className="own-teaching-point-type">{tp.test_type}</span>
                  ) : (
                    <span className="own-teaching-point-type own-teaching-point-type--global">All types</span>
                  )}
                  <button
                    className="own-teaching-point-delete"
                    onClick={() => handleDelete(tp.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        {sharedTeachingPoints.length > 0 && (
          <div className="shared-teaching-points">
            <span className="shared-teaching-points-label">Shared with you</span>
            {sharedTeachingPoints.map((sp) => (
              <div key={sp.sync_id} className="shared-teaching-point-card">
                <p className="shared-teaching-point-text">{sp.text}</p>
                <div className="shared-teaching-point-meta">
                  <span className="shared-teaching-point-sharer">
                    Shared by {sp.sharer_email}
                  </span>
                  {sp.test_type ? (
                    <span className="shared-teaching-point-type">{sp.test_type}</span>
                  ) : (
                    <span className="shared-teaching-point-type shared-teaching-point-type--global">All types</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </details>
  );
}
