-- Updated admin_list_users function with billing columns.
-- Replaces the previous version that included app_version.

DROP FUNCTION IF EXISTS admin_list_users();

CREATE OR REPLACE FUNCTION admin_list_users()
RETURNS TABLE (
    user_id uuid,
    email text,
    created_at timestamptz,
    last_sign_in_at timestamptz,
    subscription_status text,
    subscription_tier text,
    trial_end timestamptz,
    current_period_end timestamptz,
    discount_code text,
    discount_name text,
    payments_exempt boolean,
    period_report_count integer,
    period_deep_count integer
)
LANGUAGE sql SECURITY DEFINER
AS $$
    SELECT
        au.id,
        au.email,
        au.created_at,
        au.last_sign_in_at,
        s.status,
        s.tier,
        s.trial_end,
        s.current_period_end,
        s.discount_code,
        s.discount_name,
        COALESCE(ubo.payments_exempt, FALSE),
        COALESCE(up.report_count, 0),
        COALESCE(up.deep_analysis_count, 0)
    FROM auth.users au
    LEFT JOIN LATERAL (
        SELECT * FROM subscriptions sub
        WHERE sub.user_id = au.id
        ORDER BY sub.created_at DESC LIMIT 1
    ) s ON TRUE
    LEFT JOIN user_billing_overrides ubo ON ubo.user_id = au.id
    LEFT JOIN LATERAL (
        SELECT * FROM usage_periods u
        WHERE u.user_id = au.id
        ORDER BY u.period_start DESC LIMIT 1
    ) up ON TRUE
    ORDER BY au.last_sign_in_at DESC NULLS LAST;
$$;
