import { getSupabase, getSession } from "./supabase";

/**
 * Deploy a shared config value (e.g. API key) to all users via Supabase.
 * Upserts into the `shared_config` table.
 */
export async function deploySharedKey(
  key: string,
  value: string,
): Promise<void> {
  const supabase = getSupabase();
  if (!supabase) throw new Error("Supabase not configured.");

  const session = await getSession();
  if (!session?.user?.id) throw new Error("Not signed in.");

  const { error } = await supabase.from("shared_config").upsert(
    {
      key,
      value,
      updated_at: new Date().toISOString(),
      updated_by: session.user.id,
    },
    { onConflict: "key" },
  );

  if (error) throw new Error(error.message);
}

/**
 * Pull all shared config values from Supabase.
 * Returns a key-value record.
 */
export async function pullSharedConfig(): Promise<Record<string, string>> {
  const supabase = getSupabase();
  if (!supabase) return {};

  const { data, error } = await supabase.from("shared_config").select("*");

  if (error) {
    console.error("Failed to pull shared config:", error.message);
    return {};
  }

  const result: Record<string, string> = {};
  for (const row of data ?? []) {
    result[row.key] = row.value;
  }
  return result;
}
