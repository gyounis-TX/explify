import { useState, useEffect, useCallback } from "react";
import { sidecarApi } from "../../services/sidecarApi";
import { useToast } from "../shared/Toast";
import type { TeachingPoint } from "../../types/sidecar";
import "./TeachingPointsScreen.css";

export function TeachingPointsScreen() {
  const { showToast } = useToast();
  const [teachingPoints, setTeachingPoints] = useState<TeachingPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [newText, setNewText] = useState("");
  const [saving, setSaving] = useState(false);

  const fetchPoints = useCallback(async () => {
    try {
      const pts = await sidecarApi.listTeachingPoints();
      setTeachingPoints(pts);
    } catch {
      showToast("error", "Failed to load teaching points.");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchPoints();
  }, [fetchPoints]);

  const handleAdd = useCallback(async () => {
    const text = newText.trim();
    if (!text || saving) return;
    setSaving(true);
    try {
      const tp = await sidecarApi.createTeachingPoint({ text });
      setTeachingPoints((prev) => [tp, ...prev]);
      setNewText("");
      showToast("success", "Teaching point saved.");
    } catch {
      showToast("error", "Failed to save teaching point.");
    } finally {
      setSaving(false);
    }
  }, [newText, saving, showToast]);

  const handleDelete = useCallback(
    async (id: number) => {
      try {
        await sidecarApi.deleteTeachingPoint(id);
        setTeachingPoints((prev) => prev.filter((p) => p.id !== id));
        showToast("success", "Teaching point removed.");
      } catch {
        showToast("error", "Failed to delete teaching point.");
      }
    },
    [showToast],
  );

  if (loading) {
    return (
      <div className="tp-screen">
        <p>Loading teaching points...</p>
      </div>
    );
  }

  return (
    <div className="tp-screen">
      <header className="tp-header">
        <h2 className="tp-title">Teaching Points</h2>
        <p className="tp-description">
          Personalized instructions that customize how the AI interprets and
          explains results. These points can be stylistic or clinical. They are
          applied automatically during every analysis.
        </p>
      </header>

      {/* Data Entry */}
      <section className="tp-section tp-entry">
        <h3 className="tp-section-title">Add Teaching Point</h3>
        <p className="tp-section-desc">
          Write an instruction the AI should follow when generating
          explanations. For example: "Always mention diastolic dysfunction
          grading" or "De-emphasize trace regurgitation".
        </p>
        <div className="tp-entry-form">
          <textarea
            className="tp-entry-textarea"
            placeholder="e.g. Always explain the significance of E/A ratio in the context of diastolic function..."
            value={newText}
            onChange={(e) => setNewText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey && newText.trim()) {
                e.preventDefault();
                handleAdd();
              }
            }}
            rows={4}
          />
          <button
            className="tp-entry-btn"
            disabled={!newText.trim() || saving}
            onClick={handleAdd}
          >
            {saving ? "Saving..." : "Add Teaching Point"}
          </button>
        </div>
      </section>

      {/* Library */}
      <section className="tp-section tp-library">
        <h3 className="tp-section-title">
          Library
          {teachingPoints.length > 0 && (
            <span className="tp-library-count">{teachingPoints.length}</span>
          )}
        </h3>
        {teachingPoints.length === 0 ? (
          <div className="tp-empty">
            <p>No teaching points yet.</p>
            <p className="tp-empty-hint">
              Add your first teaching point above to start customizing the AI.
            </p>
          </div>
        ) : (
          <div className="tp-library-list">
            {teachingPoints.map((tp) => (
              <div key={tp.id} className="tp-card">
                <div className="tp-card-body">
                  <p className="tp-card-text">{tp.text}</p>
                  <div className="tp-card-meta">
                    {tp.test_type ? (
                      <span className="tp-card-type">{tp.test_type}</span>
                    ) : (
                      <span className="tp-card-type tp-card-type--global">
                        All types
                      </span>
                    )}
                    <span className="tp-card-date">
                      {new Date(tp.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <button
                  className="tp-card-delete"
                  onClick={() => handleDelete(tp.id)}
                  aria-label={`Delete teaching point: ${tp.text.slice(0, 30)}`}
                  title="Delete this teaching point"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
