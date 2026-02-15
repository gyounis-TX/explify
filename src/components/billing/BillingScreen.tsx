import { useState, useEffect, useCallback } from "react";
import { sidecarApi } from "../../services/sidecarApi";
import { useToast } from "../shared/Toast";
import type { BillingStatus, TierLimits } from "../../types/billing";
import "../settings/SettingsScreen.css";
import "./BillingScreen.css";

const CANCEL_REASONS = [
  "Too expensive",
  "Not using it enough",
  "Missing features I need",
  "Found a better alternative",
  "Temporary — I'll be back",
  "Other",
];

function formatLimit(value: number | null): string {
  if (value === null) return "Unlimited";
  return value.toLocaleString();
}

function UsageBar({
  label,
  used,
  limit,
}: {
  label: string;
  used: number;
  limit: number | null;
}) {
  if (limit === 0) return null;
  const pct = limit === null ? 0 : Math.min((used / limit) * 100, 100);
  const isNearLimit = limit !== null && pct >= 80;
  const isAtLimit = limit !== null && pct >= 100;

  return (
    <div className="billing-usage-bar">
      <div className="billing-usage-bar-header">
        <span className="billing-usage-bar-label">{label}</span>
        <span className="billing-usage-bar-count">
          {used.toLocaleString()} / {formatLimit(limit)}
        </span>
      </div>
      <div className="billing-usage-bar-track">
        <div
          className={`billing-usage-bar-fill ${isAtLimit ? "billing-usage-bar-fill--danger" : isNearLimit ? "billing-usage-bar-fill--warning" : ""}`}
          style={{ width: limit === null ? "0%" : `${pct}%` }}
        />
      </div>
    </div>
  );
}

function TierCard({
  tier,
  currentTier,
  onSelect,
}: {
  tier: TierLimits;
  currentTier: string | null;
  onSelect: (tier: string) => void;
}) {
  const isCurrent = tier.tier === currentTier;
  const isPopular = tier.tier === "professional";

  return (
    <div
      className={`billing-tier-card ${isCurrent ? "billing-tier-card--current" : ""} ${isPopular ? "billing-tier-card--popular" : ""}`}
    >
      {isPopular && <span className="billing-tier-badge">Most Popular</span>}
      <h4 className="billing-tier-name">{tier.display_name}</h4>
      <div className="billing-tier-price">
        <span className="billing-tier-dollar">
          ${(tier.price_monthly_cents / 100).toFixed(0)}
        </span>
        <span className="billing-tier-period">/month</span>
      </div>
      <ul className="billing-tier-features">
        <li>{formatLimit(tier.monthly_reports)} reports/month</li>
        {tier.monthly_deep_analysis !== 0 && (
          <li>{formatLimit(tier.monthly_deep_analysis)} deep analyses</li>
        )}
        {tier.monthly_letters !== 0 && (
          <li>
            {tier.monthly_letters === null
              ? "Unlimited letters"
              : `${tier.monthly_letters} letters`}
          </li>
        )}
        {tier.has_comparison && <li>Report comparison</li>}
        {tier.has_synthesis && <li>Multi-report synthesis</li>}
        {tier.has_custom_templates && <li>Custom templates</li>}
        <li>
          {tier.history_days === null
            ? "Unlimited history"
            : `${tier.history_days}-day history`}
        </li>
      </ul>
      <button
        className={`billing-tier-btn ${isCurrent ? "billing-tier-btn--current" : ""}`}
        onClick={() => onSelect(tier.tier)}
        disabled={isCurrent}
      >
        {isCurrent ? "Current Plan" : "Select Plan"}
      </button>
    </div>
  );
}

export function BillingScreen() {
  const { showToast } = useToast();
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [tiers, setTiers] = useState<TierLimits[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCancel, setShowCancel] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [cancelDetail, setCancelDetail] = useState("");
  const [canceling, setCanceling] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [s, t] = await Promise.all([
          sidecarApi.getBillingStatus(),
          sidecarApi.getBillingPrices(),
        ]);
        if (cancelled) return;
        setStatus(s);
        setTiers(t);
      } catch (err) {
        if (cancelled) return;
        const msg =
          err instanceof Error ? err.message : "Failed to load billing data";
        showToast("error", msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [showToast]);

  const handleSelectTier = useCallback(
    async (tier: string) => {
      try {
        const { url } = await sidecarApi.createCheckoutSession(tier);
        window.open(url, "_blank");
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Failed to start checkout";
        showToast("error", msg);
      }
    },
    [showToast],
  );

  const handleManageBilling = useCallback(async () => {
    try {
      const { url } = await sidecarApi.createPortalSession();
      window.open(url, "_blank");
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to open billing portal";
      showToast("error", msg);
    }
  }, [showToast]);

  const handleCancel = useCallback(async () => {
    if (!cancelReason) {
      showToast("error", "Please select a reason.");
      return;
    }
    setCanceling(true);
    try {
      await sidecarApi.cancelSubscription(cancelReason, cancelDetail);
      showToast(
        "success",
        "Subscription will cancel at the end of your billing period.",
      );
      setShowCancel(false);
      // Refresh status
      const s = await sidecarApi.getBillingStatus();
      setStatus(s);
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to cancel subscription";
      showToast("error", msg);
    } finally {
      setCanceling(false);
    }
  }, [cancelReason, cancelDetail, showToast]);

  if (loading) {
    return (
      <div className="settings-screen">
        <p>Loading billing...</p>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="settings-screen">
        <p>Unable to load billing information.</p>
      </div>
    );
  }

  const sub = status.subscription;
  const usage = status.usage;
  const limits = status.limits;

  const statusLabel =
    sub.status === "trialing"
      ? "Trial"
      : sub.status === "active"
        ? "Active"
        : sub.status === "past_due"
          ? "Past Due"
          : sub.status === "canceled"
            ? "Canceled"
            : sub.status === "paused"
              ? "Paused"
              : "No Subscription";

  const trialDaysLeft =
    sub.status === "trialing" && sub.trial_end
      ? Math.max(
          0,
          Math.ceil(
            (new Date(sub.trial_end).getTime() - Date.now()) /
              (1000 * 60 * 60 * 24),
          ),
        )
      : null;

  return (
    <div className="settings-screen">
      <header className="settings-header">
        <h2 className="settings-title">Billing</h2>
        <p className="settings-description">
          Manage your subscription, usage, and billing details.
        </p>
      </header>

      {!status.payments_enabled && (
        <div className="billing-notice">
          Billing is not currently active. All features are available without
          limits.
        </div>
      )}

      {/* Current Plan */}
      <section className="settings-section">
        <h3 className="settings-section-title">Current Plan</h3>
        <div className="billing-plan-info">
          <div className="billing-plan-tier">
            <span className="billing-plan-name">
              {limits?.display_name ?? sub.tier ?? "Free"}
            </span>
            <span className={`billing-status-badge billing-status-badge--${sub.status ?? "none"}`}>
              {statusLabel}
            </span>
          </div>
          {trialDaysLeft !== null && (
            <p className="billing-trial-info">
              {trialDaysLeft} day{trialDaysLeft !== 1 ? "s" : ""} left in trial
            </p>
          )}
          {sub.cancel_at_period_end && sub.current_period_end && (
            <p className="billing-cancel-info">
              Cancels on{" "}
              {new Date(sub.current_period_end).toLocaleDateString()}
            </p>
          )}
          {sub.discount && (
            <p className="billing-discount-info">
              Discount: {sub.discount.name}
              {sub.discount.percent ? ` (${sub.discount.percent}% off)` : ""}
              {sub.discount.months_remaining
                ? ` - ${sub.discount.months_remaining} months remaining`
                : ""}
            </p>
          )}
        </div>
      </section>

      {/* Usage This Period */}
      {status.payments_enabled && limits && (
        <section className="settings-section">
          <h3 className="settings-section-title">Usage This Period</h3>
          <div className="billing-usage-bars">
            <UsageBar
              label="Reports"
              used={usage.report_count}
              limit={limits.monthly_reports}
            />
            <UsageBar
              label="Deep Analyses"
              used={usage.deep_analysis_count}
              limit={limits.monthly_deep_analysis}
            />
            <UsageBar
              label="Letters"
              used={usage.letter_count}
              limit={limits.monthly_letters}
            />
          </div>
        </section>
      )}

      {/* Plan Options */}
      <section className="settings-section">
        <h3 className="settings-section-title">Plans</h3>
        <div className="billing-tiers-grid">
          {tiers.map((tier) => (
            <TierCard
              key={tier.tier}
              tier={tier}
              currentTier={sub.tier}
              onSelect={handleSelectTier}
            />
          ))}
        </div>
      </section>

      {/* Manage Subscription */}
      {sub.has_subscription && (
        <section className="settings-section">
          <h3 className="settings-section-title">Manage Subscription</h3>
          <div className="billing-manage-actions">
            <button className="save-btn" onClick={handleManageBilling}>
              Manage Billing
            </button>
            {!sub.cancel_at_period_end && (
              <button
                className="billing-cancel-btn"
                onClick={() => setShowCancel(true)}
              >
                Cancel Subscription
              </button>
            )}
          </div>

          {showCancel && (
            <div className="billing-cancel-form">
              <h4>Why are you canceling?</h4>
              <div className="billing-cancel-reasons">
                {CANCEL_REASONS.map((reason) => (
                  <label key={reason} className="billing-cancel-reason">
                    <input
                      type="radio"
                      name="cancel-reason"
                      value={reason}
                      checked={cancelReason === reason}
                      onChange={(e) => setCancelReason(e.target.value)}
                    />
                    {reason}
                  </label>
                ))}
              </div>
              <textarea
                className="form-input billing-cancel-detail"
                placeholder="Any additional feedback? (optional)"
                value={cancelDetail}
                onChange={(e) => setCancelDetail(e.target.value)}
                rows={3}
              />
              <div className="billing-cancel-actions">
                <button
                  className="billing-cancel-confirm"
                  onClick={handleCancel}
                  disabled={canceling || !cancelReason}
                >
                  {canceling ? "Canceling..." : "Confirm Cancellation"}
                </button>
                <button
                  className="billing-cancel-back"
                  onClick={() => setShowCancel(false)}
                >
                  Keep Subscription
                </button>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
