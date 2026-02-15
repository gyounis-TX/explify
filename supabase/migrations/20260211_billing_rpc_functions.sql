-- RPC functions for billing operations.
-- Called by the sidecar via asyncpg (not Supabase client).

-- Get active subscription for a user
CREATE OR REPLACE FUNCTION get_subscription(p_user_id UUID)
RETURNS TABLE (
    id TEXT,
    status TEXT,
    tier TEXT,
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    trial_start TIMESTAMPTZ,
    trial_end TIMESTAMPTZ,
    cancel_at_period_end BOOLEAN,
    discount_name TEXT,
    discount_percent REAL,
    discount_months_remaining INTEGER
) LANGUAGE sql STABLE AS $$
    SELECT
        s.id,
        s.status,
        s.tier,
        s.current_period_start,
        s.current_period_end,
        s.trial_start,
        s.trial_end,
        s.cancel_at_period_end,
        s.discount_name,
        s.discount_percent,
        s.discount_months_remaining
    FROM subscriptions s
    WHERE s.user_id = p_user_id
      AND s.status IN ('active', 'trialing', 'past_due', 'paused')
    ORDER BY s.created_at DESC
    LIMIT 1;
$$;

-- Get or create usage period for a user
CREATE OR REPLACE FUNCTION get_usage_period(
    p_user_id UUID,
    p_period_start TIMESTAMPTZ,
    p_period_end TIMESTAMPTZ
)
RETURNS TABLE (
    report_count INTEGER,
    deep_analysis_count INTEGER,
    batch_count INTEGER,
    letter_count INTEGER,
    comparison_count INTEGER
) LANGUAGE plpgsql AS $$
BEGIN
    -- Insert if not exists
    INSERT INTO usage_periods (user_id, period_start, period_end)
    VALUES (p_user_id, p_period_start, p_period_end)
    ON CONFLICT (user_id, period_start) DO NOTHING;

    RETURN QUERY
    SELECT
        up.report_count,
        up.deep_analysis_count,
        up.batch_count,
        up.letter_count,
        up.comparison_count
    FROM usage_periods up
    WHERE up.user_id = p_user_id
      AND up.period_start = p_period_start;
END;
$$;

-- Atomically increment a usage counter
CREATE OR REPLACE FUNCTION increment_usage(p_user_id UUID, p_feature TEXT)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    CASE p_feature
        WHEN 'report_count' THEN
            UPDATE usage_periods
            SET report_count = report_count + 1, updated_at = NOW()
            WHERE user_id = p_user_id
              AND period_start = (
                  SELECT period_start FROM usage_periods
                  WHERE user_id = p_user_id
                  ORDER BY period_start DESC LIMIT 1
              );
        WHEN 'deep_analysis_count' THEN
            UPDATE usage_periods
            SET deep_analysis_count = deep_analysis_count + 1, updated_at = NOW()
            WHERE user_id = p_user_id
              AND period_start = (
                  SELECT period_start FROM usage_periods
                  WHERE user_id = p_user_id
                  ORDER BY period_start DESC LIMIT 1
              );
        WHEN 'batch_count' THEN
            UPDATE usage_periods
            SET batch_count = batch_count + 1, updated_at = NOW()
            WHERE user_id = p_user_id
              AND period_start = (
                  SELECT period_start FROM usage_periods
                  WHERE user_id = p_user_id
                  ORDER BY period_start DESC LIMIT 1
              );
        WHEN 'letter_count' THEN
            UPDATE usage_periods
            SET letter_count = letter_count + 1, updated_at = NOW()
            WHERE user_id = p_user_id
              AND period_start = (
                  SELECT period_start FROM usage_periods
                  WHERE user_id = p_user_id
                  ORDER BY period_start DESC LIMIT 1
              );
        WHEN 'comparison_count' THEN
            UPDATE usage_periods
            SET comparison_count = comparison_count + 1, updated_at = NOW()
            WHERE user_id = p_user_id
              AND period_start = (
                  SELECT period_start FROM usage_periods
                  WHERE user_id = p_user_id
                  ORDER BY period_start DESC LIMIT 1
              );
        ELSE
            RAISE EXCEPTION 'Unknown feature: %', p_feature;
    END CASE;
END;
$$;

-- Get tier limits
CREATE OR REPLACE FUNCTION get_tier_limits(p_tier TEXT)
RETURNS TABLE (
    tier TEXT,
    display_name TEXT,
    monthly_reports INTEGER,
    monthly_deep_analysis INTEGER,
    monthly_letters INTEGER,
    max_batch_size INTEGER,
    has_comparison BOOLEAN,
    has_synthesis BOOLEAN,
    has_custom_templates BOOLEAN,
    has_teaching_points_create BOOLEAN,
    has_full_personalization BOOLEAN,
    history_days INTEGER,
    price_monthly_cents INTEGER,
    price_annual_cents INTEGER
) LANGUAGE sql STABLE AS $$
    SELECT
        tl.tier,
        tl.display_name,
        tl.monthly_reports,
        tl.monthly_deep_analysis,
        tl.monthly_letters,
        tl.max_batch_size,
        tl.has_comparison,
        tl.has_synthesis,
        tl.has_custom_templates,
        tl.has_teaching_points_create,
        tl.has_full_personalization,
        tl.history_days,
        tl.price_monthly_cents,
        tl.price_annual_cents
    FROM tier_limits tl
    WHERE tl.tier = p_tier;
$$;

-- Get all billing config as key/value pairs
CREATE OR REPLACE FUNCTION get_billing_config()
RETURNS TABLE (key TEXT, value TEXT) LANGUAGE sql STABLE AS $$
    SELECT bc.key, bc.value FROM billing_config bc;
$$;

-- Check user billing overrides
CREATE OR REPLACE FUNCTION check_user_billing_override(p_user_id UUID)
RETURNS TABLE (
    payments_exempt BOOLEAN,
    custom_trial_days INTEGER,
    custom_tier TEXT,
    notes TEXT
) LANGUAGE sql STABLE AS $$
    SELECT
        ubo.payments_exempt,
        ubo.custom_trial_days,
        ubo.custom_tier,
        ubo.notes
    FROM user_billing_overrides ubo
    WHERE ubo.user_id = p_user_id;
$$;

-- Upsert customer mapping
CREATE OR REPLACE FUNCTION upsert_customer(p_user_id UUID, p_stripe_customer_id TEXT)
RETURNS VOID LANGUAGE sql AS $$
    INSERT INTO customers (user_id, stripe_customer_id)
    VALUES (p_user_id, p_stripe_customer_id)
    ON CONFLICT (user_id)
    DO UPDATE SET stripe_customer_id = EXCLUDED.stripe_customer_id;
$$;

-- Upsert subscription from webhook data
CREATE OR REPLACE FUNCTION upsert_subscription(
    p_id TEXT,
    p_user_id UUID,
    p_price_id TEXT,
    p_status TEXT,
    p_tier TEXT,
    p_current_period_start TIMESTAMPTZ,
    p_current_period_end TIMESTAMPTZ,
    p_trial_start TIMESTAMPTZ DEFAULT NULL,
    p_trial_end TIMESTAMPTZ DEFAULT NULL,
    p_cancel_at_period_end BOOLEAN DEFAULT FALSE,
    p_canceled_at TIMESTAMPTZ DEFAULT NULL,
    p_ended_at TIMESTAMPTZ DEFAULT NULL
)
RETURNS VOID LANGUAGE sql AS $$
    INSERT INTO subscriptions (
        id, user_id, price_id, status, tier,
        current_period_start, current_period_end,
        trial_start, trial_end,
        cancel_at_period_end, canceled_at, ended_at,
        updated_at
    ) VALUES (
        p_id, p_user_id, p_price_id, p_status, p_tier,
        p_current_period_start, p_current_period_end,
        p_trial_start, p_trial_end,
        p_cancel_at_period_end, p_canceled_at, p_ended_at,
        NOW()
    )
    ON CONFLICT (id) DO UPDATE SET
        status = EXCLUDED.status,
        tier = EXCLUDED.tier,
        price_id = EXCLUDED.price_id,
        current_period_start = EXCLUDED.current_period_start,
        current_period_end = EXCLUDED.current_period_end,
        trial_start = EXCLUDED.trial_start,
        trial_end = EXCLUDED.trial_end,
        cancel_at_period_end = EXCLUDED.cancel_at_period_end,
        canceled_at = EXCLUDED.canceled_at,
        ended_at = EXCLUDED.ended_at,
        updated_at = NOW();
$$;

-- Record cancellation reason
CREATE OR REPLACE FUNCTION record_cancellation(
    p_user_id UUID,
    p_subscription_id TEXT,
    p_reason TEXT,
    p_detail TEXT
)
RETURNS VOID LANGUAGE sql AS $$
    INSERT INTO subscription_cancellations (user_id, subscription_id, reason, reason_detail)
    VALUES (p_user_id, p_subscription_id, p_reason, p_detail);
$$;
