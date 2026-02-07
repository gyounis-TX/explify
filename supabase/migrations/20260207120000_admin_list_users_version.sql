-- Drop existing function so we can change the return type
DROP FUNCTION IF EXISTS admin_list_users();

-- Recreate with app_version column
CREATE OR REPLACE FUNCTION admin_list_users()
RETURNS TABLE (
  user_id uuid,
  email text,
  created_at timestamptz,
  app_version text
)
LANGUAGE sql SECURITY DEFINER
AS $$
  SELECT
    au.id,
    au.email,
    au.created_at,
    s.value AS app_version
  FROM auth.users au
  LEFT JOIN settings s ON s.user_id = au.id AND s.key = 'app_version'
  ORDER BY au.created_at DESC;
$$;
