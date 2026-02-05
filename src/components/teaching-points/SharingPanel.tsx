import { useState, useEffect, useCallback } from "react";
import {
  getMyShareRecipients,
  getMyShareSources,
  addShareRecipient,
  removeShareRecipient,
  type ShareRecipient,
  type ShareSource,
} from "../../services/sharingService";
import { getSupabase, getSession } from "../../services/supabase";
import { useToast } from "../shared/Toast";

export function SharingPanel() {
  const { showToast } = useToast();
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [loading, setLoading] = useState(true);
  const [recipients, setRecipients] = useState<ShareRecipient[]>([]);
  const [sources, setSources] = useState<ShareSource[]>([]);
  const [email, setEmail] = useState("");
  const [adding, setAdding] = useState(false);

  const checkAuth = useCallback(async () => {
    const supabase = getSupabase();
    if (!supabase) {
      setIsSignedIn(false);
      setLoading(false);
      return;
    }
    const session = await getSession();
    setIsSignedIn(!!session?.user);
    setLoading(false);
  }, []);

  const fetchSharing = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([
        getMyShareRecipients(),
        getMyShareSources(),
      ]);
      setRecipients(r);
      setSources(s);
    } catch {
      // Silently fail — user may not be signed in
    }
  }, []);

  useEffect(() => {
    checkAuth().then(() => fetchSharing());
  }, [checkAuth, fetchSharing]);

  const handleAdd = useCallback(async () => {
    const trimmed = email.trim();
    if (!trimmed || adding) return;
    setAdding(true);
    try {
      await addShareRecipient(trimmed);
      setEmail("");
      showToast("success", `Now sharing with ${trimmed}.`);
      await fetchSharing();
    } catch (err) {
      showToast(
        "error",
        err instanceof Error ? err.message : "Failed to add share.",
      );
    } finally {
      setAdding(false);
    }
  }, [email, adding, showToast, fetchSharing]);

  const handleRemove = useCallback(
    async (shareId: number, recipientEmail: string) => {
      try {
        await removeShareRecipient(shareId);
        setRecipients((prev) => prev.filter((r) => r.share_id !== shareId));
        showToast("success", `Stopped sharing with ${recipientEmail}.`);
      } catch {
        showToast("error", "Failed to remove share.");
      }
    },
    [showToast],
  );

  if (loading) return null;

  if (!isSignedIn) {
    return (
      <section className="settings-section sharing-panel">
        <h3 className="settings-section-title">Sharing</h3>
        <div className="sharing-signin">
          <p>
            Sign in to share teaching points and templates with other users.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="settings-section sharing-panel">
      <h3 className="settings-section-title">Sharing</h3>
      <p className="sharing-desc">
        Share your teaching points and templates with colleagues. They will see
        your content as read-only and it will be included in their reports.
      </p>

      {/* Sharing My Content With */}
      <div className="sharing-subsection">
        <h4 className="sharing-subtitle">Sharing My Content With</h4>
        <div className="sharing-add">
          <input
            className="sharing-input"
            type="email"
            placeholder="colleague@clinic.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && email.trim()) {
                e.preventDefault();
                handleAdd();
              }
            }}
          />
          <button
            className="sharing-add-btn"
            onClick={handleAdd}
            disabled={!email.trim() || adding}
          >
            {adding ? "Adding..." : "Share"}
          </button>
        </div>
        {recipients.length === 0 ? (
          <p className="sharing-empty">Not sharing with anyone yet.</p>
        ) : (
          <ul className="sharing-list">
            {recipients.map((r) => (
              <li key={r.share_id} className="sharing-item">
                <span className="sharing-email">{r.recipient_email}</span>
                <span className="sharing-date">
                  {new Date(r.created_at).toLocaleDateString()}
                </span>
                <button
                  className="sharing-remove-btn"
                  onClick={() => handleRemove(r.share_id, r.recipient_email)}
                  title={`Stop sharing with ${r.recipient_email}`}
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Shared With Me */}
      <div className="sharing-subsection">
        <h4 className="sharing-subtitle">Shared With Me</h4>
        {sources.length === 0 ? (
          <p className="sharing-empty">No one is sharing with you yet.</p>
        ) : (
          <>
            <p className="sharing-info">
              Teaching points and templates from these users are included in your
              reports.
            </p>
            <ul className="sharing-list">
              {sources.map((s) => (
                <li key={s.share_id} className="sharing-item">
                  <span className="sharing-email">{s.sharer_email}</span>
                  <span className="sharing-date">
                    {new Date(s.created_at).toLocaleDateString()}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
