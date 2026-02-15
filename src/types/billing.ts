export interface SubscriptionStatus {
  has_subscription: boolean;
  tier: "starter" | "professional" | "unlimited" | null;
  status: "active" | "trialing" | "past_due" | "canceled" | "paused" | null;
  trial_end: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  discount?: { name: string; percent?: number; months_remaining?: number };
}

export interface UsageMetrics {
  report_count: number;
  deep_analysis_count: number;
  letter_count: number;
  comparison_count: number;
  batch_count: number;
}

export interface TierLimits {
  tier: string;
  display_name: string;
  monthly_reports: number | null;
  monthly_deep_analysis: number | null;
  monthly_letters: number | null;
  max_batch_size: number;
  has_comparison: boolean;
  has_synthesis: boolean;
  has_custom_templates: boolean;
  has_teaching_points_create: boolean;
  has_full_personalization: boolean;
  history_days: number | null;
  price_monthly_cents: number;
  price_annual_cents: number;
}

export interface BillingStatus {
  subscription: SubscriptionStatus;
  usage: UsageMetrics;
  limits: TierLimits;
  payments_enabled: boolean;
}

export interface BillingError {
  detail: string;
  tier: string;
  feature: string;
  limit: number;
  used: number;
  upgrade_url: string;
}
