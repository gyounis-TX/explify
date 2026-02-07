import { useState, useEffect, useMemo } from "react";
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
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [editingTypeId, setEditingTypeId] = useState<number | null>(null);
  const [validTypes, setValidTypes] = useState<{ id: string; name: string }[]>([]);

  useEffect(() => {
    sidecarApi.listTestTypes().then(setValidTypes).catch(() => {});
  }, []);

  const totalCount = teachingPoints.length + sharedTeachingPoints.length;

  // Deduplicated sorted set of all test_type values across own + shared points
  const uniqueTypes = useMemo(() => {
    const types = new Set<string>();
    for (const tp of teachingPoints) {
      if (tp.test_type) types.add(tp.test_type);
    }
    for (const sp of sharedTeachingPoints) {
      if (sp.test_type) types.add(sp.test_type);
    }
    return [...types].sort();
  }, [teachingPoints, sharedTeachingPoints]);

  // All valid types for the datalist (registry + any already used), with display names
  const allTypeOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const t of validTypes) map.set(t.id, t.name);
    for (const t of uniqueTypes) {
      if (!map.has(t)) map.set(t, t.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()));
    }
    if (effectiveTestType && !map.has(effectiveTestType)) {
      map.set(effectiveTestType, effectiveTestType.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()));
    }
    return [...map.entries()].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name));
  }, [validTypes, uniqueTypes, effectiveTestType]);

  /** Try to match free-text input to a valid registry type ID. */
  const resolveTypeId = (input: string): string | null => {
    if (!input) return null;
    const lower = input.toLowerCase().replace(/[\s_-]+/g, "_");
    const exact = validTypes.find((t) => t.id === lower);
    if (exact) return exact.id;
    const byName = validTypes.find((t) => t.name.toLowerCase() === input.toLowerCase());
    if (byName) return byName.id;
    const partial = validTypes.find(
      (t) => t.id.includes(lower) || t.name.toLowerCase().includes(input.toLowerCase()),
    );
    if (partial) return partial.id;
    return null;
  };

  const getDisplayName = (typeId: string): string => {
    const found = validTypes.find(t => t.id === typeId);
    return found?.name ?? typeId.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
  };

  // Filter logic: "" = all, "__global__" = only null test_type, specific = that type + global
  const filteredTeachingPoints = useMemo(() => {
    if (!typeFilter) return teachingPoints;
    if (typeFilter === "__global__") return teachingPoints.filter((tp) => !tp.test_type);
    return teachingPoints.filter((tp) => !tp.test_type || tp.test_type === typeFilter);
  }, [teachingPoints, typeFilter]);

  const filteredSharedPoints = useMemo(() => {
    if (!typeFilter) return sharedTeachingPoints;
    if (typeFilter === "__global__") return sharedTeachingPoints.filter((sp) => !sp.test_type);
    return sharedTeachingPoints.filter((sp) => !sp.test_type || sp.test_type === typeFilter);
  }, [sharedTeachingPoints, typeFilter]);

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

  const handleTypeChange = async (id: number, rawInput: string | null) => {
    setEditingTypeId(null);
    const prev = teachingPoints.find((tp) => tp.id === id);
    if (!prev) return;

    // Blank = "All types"
    if (!rawInput) {
      if (prev.test_type === null) return;
      setTeachingPoints((pts) =>
        pts.map((tp) => (tp.id === id ? { ...tp, test_type: null } : tp)),
      );
      try {
        await sidecarApi.updateTeachingPoint(id, { test_type: null });
        queueUpsertAfterMutation("teaching_points", id).catch(() => {});
      } catch {
        setTeachingPoints((pts) =>
          pts.map((tp) => (tp.id === id ? { ...tp, test_type: prev.test_type } : tp)),
        );
        showToast("error", "Failed to update teaching point type.");
      }
      return;
    }

    const resolved = resolveTypeId(rawInput);
    if (!resolved) {
      showToast("info", "No matching type found. Try picking from the suggestions.");
      return;
    }
    if (resolved === prev.test_type) return;

    setTeachingPoints((pts) =>
      pts.map((tp) => (tp.id === id ? { ...tp, test_type: resolved } : tp)),
    );
    try {
      await sidecarApi.updateTeachingPoint(id, { test_type: resolved });
      queueUpsertAfterMutation("teaching_points", id).catch(() => {});
    } catch {
      setTeachingPoints((pts) =>
        pts.map((tp) => (tp.id === id ? { ...tp, test_type: prev.test_type } : tp)),
      );
      showToast("error", "Failed to update teaching point type.");
    }
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

        {/* Filter dropdown */}
        {uniqueTypes.length > 0 && (
          <div className="teaching-points-filter-row">
            <select
              className="teaching-points-filter-select"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
            >
              <option value="">All teaching points</option>
              <option value="__global__">Global only</option>
              {uniqueTypes.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        )}

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
        {filteredTeachingPoints.length > 0 && (
          <div className="own-teaching-points">
            <span className="own-teaching-points-label">Your teaching points</span>
            {filteredTeachingPoints.map((tp) => (
              <div key={tp.id} className="own-teaching-point-card">
                <p className="own-teaching-point-text">{tp.text}</p>
                <div className="own-teaching-point-meta">
                  {editingTypeId === tp.id ? (
                    <>
                      <input
                        className="own-teaching-point-type-select"
                        list={`tp-type-list-${tp.id}`}
                        defaultValue={tp.test_type ? getDisplayName(tp.test_type) : ""}
                        placeholder="Type or pick (blank = all)"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            const val = (e.target as HTMLInputElement).value.trim() || null;
                            handleTypeChange(tp.id, val);
                          } else if (e.key === "Escape") {
                            setEditingTypeId(null);
                          }
                        }}
                        onBlur={(e) => {
                          const val = e.target.value.trim() || null;
                          handleTypeChange(tp.id, val);
                        }}
                      />
                      <datalist id={`tp-type-list-${tp.id}`}>
                        {allTypeOptions.map((t) => (
                          <option key={t.id} value={t.name} />
                        ))}
                      </datalist>
                    </>
                  ) : tp.test_type ? (
                    <>
                      <span
                        className="own-teaching-point-type"
                        onClick={() => setEditingTypeId(tp.id)}
                        title="Click to change type"
                      >
                        {tp.test_type}
                      </span>
                      <span
                        className="own-teaching-point-type own-teaching-point-type--display"
                        onClick={() => setEditingTypeId(tp.id)}
                        title="Click to change type"
                      >
                        {getDisplayName(tp.test_type)}
                      </span>
                    </>
                  ) : (
                    <span
                      className="own-teaching-point-type own-teaching-point-type--global"
                      onClick={() => setEditingTypeId(tp.id)}
                      title="Click to change type"
                    >
                      All types
                    </span>
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
        {filteredSharedPoints.length > 0 && (
          <div className="shared-teaching-points">
            <span className="shared-teaching-points-label">Shared with you</span>
            {filteredSharedPoints.map((sp) => (
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
