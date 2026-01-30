import { useState, useEffect, useCallback } from "react";
import { sidecarApi } from "../../services/sidecarApi";
import { useToast } from "../shared/Toast";
import type { LetterResponse } from "../../types/sidecar";
import "./LettersScreen.css";

export function LettersScreen() {
  const { showToast } = useToast();
  const [letters, setLetters] = useState<LetterResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const fetchLetters = useCallback(async () => {
    setLoading(true);
    try {
      const res = await sidecarApi.listLetters();
      setLetters(res.items);
    } catch {
      showToast("error", "Failed to load letters.");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchLetters();
  }, [fetchLetters]);

  const handleCopy = useCallback(
    async (content: string) => {
      try {
        await navigator.clipboard.writeText(content);
        showToast("success", "Copied to clipboard.");
      } catch {
        showToast("error", "Failed to copy.");
      }
    },
    [showToast],
  );

  const handleDelete = useCallback(
    async (id: number) => {
      if (!window.confirm("Delete this letter?")) return;
      setDeletingId(id);
      try {
        await sidecarApi.deleteLetter(id);
        setLetters((prev) => prev.filter((l) => l.id !== id));
        showToast("success", "Letter deleted.");
      } catch {
        showToast("error", "Failed to delete letter.");
      } finally {
        setDeletingId(null);
      }
    },
    [showToast],
  );

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  return (
    <div className="letters-screen">
      <header className="letters-header">
        <h2 className="letters-title">Letters</h2>
        <p className="letters-description">
          Generated explanations, questions, and letters for patients.
        </p>
      </header>

      {loading ? (
        <div className="letters-loading">
          <div className="spinner" />
          <p>Loading letters...</p>
        </div>
      ) : letters.length === 0 ? (
        <div className="letters-empty">
          <p>
            No letters yet. Use the "Help Me" section on the Import screen to
            generate patient-facing content.
          </p>
        </div>
      ) : (
        <div className="letters-list">
          {letters.map((letter) => {
            const isExpanded = expandedId === letter.id;
            return (
              <div key={letter.id} className="letter-card">
                <div className="letter-card-header">
                  <span className="letter-type-badge">
                    {letter.letter_type}
                  </span>
                  <span className="letter-date">
                    {formatDate(letter.created_at)}
                  </span>
                </div>
                <p className="letter-prompt">{letter.prompt}</p>
                <div
                  className={`letter-content${!isExpanded ? " letter-content--collapsed" : ""}`}
                >
                  {letter.content}
                </div>
                <div className="letter-actions">
                  <button
                    className="letter-action-btn"
                    onClick={() =>
                      setExpandedId(isExpanded ? null : letter.id)
                    }
                  >
                    {isExpanded ? "Collapse" : "Expand"}
                  </button>
                  <button
                    className="letter-action-btn"
                    onClick={() => handleCopy(letter.content)}
                  >
                    Copy
                  </button>
                  <button
                    className="letter-action-btn letter-action-btn--danger"
                    onClick={() => handleDelete(letter.id)}
                    disabled={deletingId === letter.id}
                  >
                    {deletingId === letter.id ? "Deleting..." : "Delete"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
