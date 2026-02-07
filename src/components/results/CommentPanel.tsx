interface CommentPanelProps {
  commentMode: "long" | "short" | "sms";
  setCommentMode: (mode: "long" | "short" | "sms") => void;
  isEditing: boolean;
  editedSummary: string;
  setEditedSummary: (value: string) => void;
  onMarkDirty: () => void;
  commentPreviewText: string;
  isGeneratingComment: boolean;
  isGeneratingLong: boolean;
  isGeneratingSms: boolean;
  onCopy: () => void;
  onExportPdf: () => void;
  isExporting: boolean;
  isLiked: boolean;
  onToggleLike: () => void;
  smsEnabled: boolean;
}

export function CommentPanel({
  commentMode,
  setCommentMode,
  isEditing,
  editedSummary,
  setEditedSummary,
  onMarkDirty,
  commentPreviewText,
  isGeneratingComment,
  isGeneratingLong,
  isGeneratingSms,
  onCopy,
  onExportPdf,
  isExporting,
  isLiked,
  onToggleLike,
  smsEnabled,
}: CommentPanelProps) {
  const isLoading =
    (isGeneratingComment && commentMode === "short") ||
    (isGeneratingLong && commentMode === "long") ||
    (isGeneratingSms && commentMode === "sms");

  return (
    <div className="results-comment-panel">
      <div className="comment-panel-header">
        <h3>Result Comment</h3>
        <button
          className={`like-btn${isLiked ? " like-btn--active" : ""}`}
          onClick={onToggleLike}
        >
          {isLiked ? "\u2665 Liked" : "\u2661 Like"}
        </button>
      </div>
      <div className="comment-type-toggle">
        <button
          className={`comment-type-btn${commentMode === "short" ? " comment-type-btn--active" : ""}`}
          onClick={() => setCommentMode("short")}
        >
          Short Comment
        </button>
        <button
          className={`comment-type-btn${commentMode === "long" ? " comment-type-btn--active" : ""}`}
          onClick={() => setCommentMode("long")}
        >
          Long Comment
        </button>
        {smsEnabled && (
          <button
            className={`comment-type-btn${commentMode === "sms" ? " comment-type-btn--active" : ""}`}
            onClick={() => setCommentMode("sms")}
          >
            SMS
          </button>
        )}
      </div>
      {isEditing && (
        <textarea
          className="summary-textarea"
          value={editedSummary}
          onChange={(e) => {
            setEditedSummary(e.target.value);
            onMarkDirty();
          }}
          rows={6}
        />
      )}
      {isLoading ? (
        <div className="comment-generating">
          {commentMode === "sms"
            ? "Generating SMS summary..."
            : commentMode === "short"
              ? "Generating short comment..."
              : "Generating detailed explanation..."}
        </div>
      ) : (
        <div className="comment-preview">{commentPreviewText}</div>
      )}
      <span className="comment-char-count">{commentPreviewText.length} chars</span>
      <button className="comment-copy-btn" onClick={onCopy}>
        Copy to Clipboard
      </button>
      <div className="comment-export-row">
        <button
          className="comment-export-btn"
          onClick={onExportPdf}
          disabled={isExporting}
        >
          {isExporting ? "Exporting\u2026" : "Export PDF"}
        </button>
        <button className="comment-export-btn" onClick={() => window.print()}>
          Print
        </button>
      </div>
    </div>
  );
}
