-- Usage tracking migration
-- Run this in the Supabase SQL Editor

-- usage_log table
CREATE TABLE IF NOT EXISTS usage_log (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  model_used text NOT NULL,
  input_tokens integer NOT NULL DEFAULT 0,
  output_tokens integer NOT NULL DEFAULT 0,
  request_type text NOT NULL DEFAULT 'explain',  -- 'explain' | 'letter'
  deep_analysis boolean NOT NULL DEFAULT false
);

-- Indexes
CREATE INDEX idx_usage_log_user_id ON usage_log(user_id);
CREATE INDEX idx_usage_log_created_at ON usage_log(created_at);

-- RLS: users can only insert their own rows
ALTER TABLE usage_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users insert own usage" ON usage_log
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Admin aggregation function (bypasses RLS)
CREATE OR REPLACE FUNCTION admin_usage_summary(since timestamptz)
RETURNS TABLE (
  user_id uuid,
  email text,
  total_queries bigint,
  total_input_tokens bigint,
  total_output_tokens bigint,
  sonnet_queries bigint,
  sonnet_input_tokens bigint,
  sonnet_output_tokens bigint,
  opus_queries bigint,
  opus_input_tokens bigint,
  opus_output_tokens bigint,
  deep_analysis_count bigint,
  last_active timestamptz
)
LANGUAGE sql SECURITY DEFINER
AS $$
  SELECT
    u.user_id,
    au.email,
    count(*)::bigint AS total_queries,
    coalesce(sum(u.input_tokens), 0)::bigint,
    coalesce(sum(u.output_tokens), 0)::bigint,
    count(*) FILTER (WHERE u.model_used ILIKE '%sonnet%')::bigint,
    coalesce(sum(u.input_tokens) FILTER (WHERE u.model_used ILIKE '%sonnet%'), 0)::bigint,
    coalesce(sum(u.output_tokens) FILTER (WHERE u.model_used ILIKE '%sonnet%'), 0)::bigint,
    count(*) FILTER (WHERE u.model_used ILIKE '%opus%')::bigint,
    coalesce(sum(u.input_tokens) FILTER (WHERE u.model_used ILIKE '%opus%'), 0)::bigint,
    coalesce(sum(u.output_tokens) FILTER (WHERE u.model_used ILIKE '%opus%'), 0)::bigint,
    count(*) FILTER (WHERE u.deep_analysis)::bigint,
    max(u.created_at)
  FROM usage_log u
  JOIN auth.users au ON au.id = u.user_id
  WHERE u.created_at >= since
  GROUP BY u.user_id, au.email
  ORDER BY total_queries DESC;
$$;

-- List all registered users (even those with no usage)
CREATE OR REPLACE FUNCTION admin_list_users()
RETURNS TABLE (
  user_id uuid,
  email text,
  created_at timestamptz
)
LANGUAGE sql SECURITY DEFINER
AS $$
  SELECT id, email, created_at FROM auth.users ORDER BY created_at DESC;
$$;
