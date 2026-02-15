import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { sidecarApi } from "../../services/sidecarApi";
import type { BillingError } from "../../types/billing";
import "./UpgradeModal.css";

const TIER_ORDER = ["starter", "professional", "unlimited"];

function getNextTier(currentTier: string | null): string {
  if (!currentTier) return "starter";
  const idx = TIER_ORDER.indexOf(currentTier);
  if (idx < 0 || idx >= TIER_ORDER.length - 1) return "unlimited";
  return TIER_ORDER[idx + 1];
}

function tierDisplayName(tier: string): string {
  return tier.charAt(0).toUpperCase() + tier.slice(1);
}

export function UpgradeModal() {
  const navigate = useNavigate();
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState<BillingError | null>(null);
  const [upgrading, setUpgrading] = useState(false);

  useEffect(() => {
    function handleLimitReached(e: Event) {
      const detail = (e as CustomEvent).detail as BillingError;
      setError(detail);
      setVisible(true);
    }

    window.addEventListener("billing:limit-reached", handleLimitReached);
    return () => {
      window.removeEventListener("billing:limit-reached", handleLimitReached);
    };
  }, []);

  const handleUpgrade = useCallback(async () => {
    if (!error) return;
    setUpgrading(true);
    try {
      const nextTier = getNextTier(error.tier);
      const { url } = await sidecarApi.createCheckoutSession(nextTier);
      window.open(url, "_blank");
      setVisible(false);
    } catch {
      // Error already shown by sidecarApi
    } finally {
      setUpgrading(false);
    }
  }, [error]);

  const handleViewUsage = useCallback(() => {
    setVisible(false);
    navigate("/billing");
  }, [navigate]);

  if (!visible || !error) return null;

  const nextTier = getNextTier(error.tier);

  return (
    <div className="upgrade-modal-overlay" onClick={() => setVisible(false)}>
      <div
        className="upgrade-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          className="upgrade-modal-close"
          onClick={() => setVisible(false)}
          aria-label="Close"
        >
          &times;
        </button>

        <h3 className="upgrade-modal-title">Usage Limit Reached</h3>
        <p className="upgrade-modal-message">
          You've used all{" "}
          <strong>
            {error.limit.toLocaleString()} {error.feature}
          </strong>{" "}
          included in your {tierDisplayName(error.tier)} plan this month.
        </p>

        <div className="upgrade-modal-actions">
          <button
            className="upgrade-modal-upgrade-btn"
            onClick={handleUpgrade}
            disabled={upgrading}
          >
            {upgrading
              ? "Loading..."
              : `Upgrade to ${tierDisplayName(nextTier)}`}
          </button>
          <button
            className="upgrade-modal-usage-btn"
            onClick={handleViewUsage}
          >
            View Usage
          </button>
        </div>
      </div>
    </div>
  );
}
