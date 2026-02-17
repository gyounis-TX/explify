import "./ResultsScreen.css";

interface CombinedSummaryPanelProps {
  isGenerating: boolean;
  error: string | null;
  summary: string | null;
  editedSummary: string;
  isEditing: boolean;
  onEditedSummaryChange: (value: string) => void;
  onToggleEditing: () => void;
  onRegenerate: () => void;
  onCopy: () => Promise<void>;
}

export function CombinedSummaryPanel({
  isGenerating,
  error,
  summary,
  editedSummary,
  isEditing,
  onEditedSummaryChange,
  onToggleEditing,
  onRegenerate,
  onCopy,
}: CombinedSummaryPanelProps) {
  return (
    <div className="combined-summary-panel">
      {isGenerating && (
        <div className="combined-summary-loading">
          <div className="spinner" />
          <span>Generating combined summary...</span>
        </div>
      )}
      {error && (
        <div className="import-error">
          <p>{error}</p>
          <button className="refine-btn" onClick={onRegenerate}>
            Retry
          </button>
        </div>
      )}
      {summary && !isGenerating && (
        <>
          <div className="combined-summary-header">
            <h3>Combined Summary</h3>
          </div>
          {isEditing ? (
            <textarea
              className="summary-textarea"
              autoComplete="off"
              value={editedSummary}
              onChange={(e) => onEditedSummaryChange(e.target.value)}
              rows={12}
            />
          ) : (
            <div className="comment-preview">
              {editedSummary}
            </div>
          )}
          <span className="comment-char-count">
            {editedSummary.length} chars
          </span>
          <div className="combined-summary-actions">
            <button className="comment-copy-btn" onClick={onCopy}>
              Copy to Clipboard
            </button>
            <button
              className={`edit-toggle-btn${isEditing ? " edit-toggle-btn--active" : ""}`}
              onClick={onToggleEditing}
            >
              {isEditing ? "Done Editing" : "Edit"}
            </button>
            <button
              className="refine-btn"
              onClick={onRegenerate}
              disabled={isGenerating}
            >
              Regenerate
            </button>
          </div>
        </>
      )}
    </div>
  );
}
