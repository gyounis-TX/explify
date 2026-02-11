-- Billing tables for Stripe subscription management.
-- Run this migration in your Supabase SQL editor after creating
-- Stripe products and prices.

-- Stripe customer mapping
CREATE TABLE IF NOT EXISTS customers (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Stripe products (synced via webhooks)
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Stripe prices (synced via webhooks)
CREATE TABLE IF NOT EXISTS prices (
    id TEXT PRIMARY KEY,
    product_id TEXT REFERENCES products(id) ON DELETE CASCADE,
    unit_amount INTEGER NOT NULL,
    currency TEXT DEFAULT 'usd',
    interval TEXT DEFAULT 'month',
    interval_count INTEGER DEFAULT 1,
    trial_period_days INTEGER,
    active BOOLEAN DEFAULT TRUE,
    tier TEXT,  -- 'starter' | 'professional' | 'unlimited'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Stripe subscriptions (synced via webhooks)
CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    price_id TEXT REFERENCES prices(id),
    status TEXT NOT NULL,
    tier TEXT,
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    trial_start TIMESTAMPTZ,
    trial_end TIMESTAMPTZ,
    cancel_at TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    canceled_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    paused_at TIMESTAMPTZ,
    discount_code TEXT,
    discount_percent REAL,
    discount_amount_off INTEGER,
    discount_name TEXT,
    discount_duration TEXT,
    discount_months_remaining INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);

-- Usage tracking per billing period
CREATE TABLE IF NOT EXISTS usage_periods (
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    report_count INTEGER DEFAULT 0,
    deep_analysis_count INTEGER DEFAULT 0,
    batch_count INTEGER DEFAULT 0,
    letter_count INTEGER DEFAULT 0,
    comparison_count INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, period_start)
);

-- Admin billing configuration
CREATE TABLE IF NOT EXISTS billing_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO billing_config (key, value) VALUES
    ('payments_enabled', 'false'),
    ('trial_period_days', '14'),
    ('trial_tier', 'professional'),
    ('grace_period_hours', '72'),
    ('require_payment_method_for_trial', 'false'),
    ('retention_coupon_id', ''),
    ('retention_offer_text', 'Stay for 50% off for 3 months')
ON CONFLICT (key) DO NOTHING;

-- Tier feature limits (admin-editable)
CREATE TABLE IF NOT EXISTS tier_limits (
    tier TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    monthly_reports INTEGER,         -- NULL = unlimited
    monthly_deep_analysis INTEGER,   -- NULL = unlimited
    monthly_letters INTEGER,         -- NULL = unlimited
    max_batch_size INTEGER DEFAULT 1,
    has_comparison BOOLEAN DEFAULT FALSE,
    has_synthesis BOOLEAN DEFAULT FALSE,
    has_custom_templates BOOLEAN DEFAULT FALSE,
    has_teaching_points_create BOOLEAN DEFAULT FALSE,
    has_full_personalization BOOLEAN DEFAULT FALSE,
    history_days INTEGER,            -- NULL = unlimited
    price_monthly_cents INTEGER,
    price_annual_cents INTEGER,
    sort_order INTEGER DEFAULT 0
);

INSERT INTO tier_limits VALUES
    ('starter', 'Starter', 75, 0, 0, 1, FALSE, FALSE, FALSE, FALSE, FALSE, 30, 2900, 29000, 1),
    ('professional', 'Professional', 300, 10, NULL, 3, TRUE, TRUE, TRUE, TRUE, TRUE, NULL, 4900, 49000, 2),
    ('unlimited', 'Unlimited', NULL, NULL, NULL, 10, TRUE, TRUE, TRUE, TRUE, TRUE, NULL, 9900, 99000, 3)
ON CONFLICT (tier) DO NOTHING;

-- Per-user billing overrides
CREATE TABLE IF NOT EXISTS user_billing_overrides (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    payments_exempt BOOLEAN DEFAULT FALSE,
    custom_trial_days INTEGER,
    custom_tier TEXT,
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by TEXT
);

-- Cancellation reasons (analytics)
CREATE TABLE IF NOT EXISTS subscription_cancellations (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    subscription_id TEXT,
    reason TEXT,
    reason_detail TEXT,
    retention_offered BOOLEAN DEFAULT FALSE,
    retention_accepted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Admin-created discount codes
CREATE TABLE IF NOT EXISTS admin_discount_codes (
    id SERIAL PRIMARY KEY,
    stripe_coupon_id TEXT NOT NULL,
    stripe_promo_code_id TEXT,
    code TEXT NOT NULL,
    description TEXT,
    discount_type TEXT NOT NULL,      -- 'percent' | 'amount' | 'trial_extension'
    discount_value REAL NOT NULL,
    duration TEXT NOT NULL,           -- 'once' | 'repeating' | 'forever'
    duration_months INTEGER,
    max_redemptions INTEGER,
    expires_at TIMESTAMPTZ,
    first_time_only BOOLEAN DEFAULT FALSE,
    active BOOLEAN DEFAULT TRUE,
    times_redeemed INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- Webhook event deduplication
CREATE TABLE IF NOT EXISTS stripe_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS policies
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE tier_limits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users view own subscription" ON subscriptions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users view own customer" ON customers FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users view own usage" ON usage_periods FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Products readable" ON products FOR SELECT USING (true);
CREATE POLICY "Prices readable" ON prices FOR SELECT USING (true);
CREATE POLICY "Config readable" ON billing_config FOR SELECT USING (true);
CREATE POLICY "Tiers readable" ON tier_limits FOR SELECT USING (true);
