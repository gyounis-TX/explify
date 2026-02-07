import { getSupabase } from "./supabase";

interface UsageEntry {
  model_used: string;
  input_tokens: number;
  output_tokens: number;
  request_type: "explain" | "letter" | "synthesize";
  deep_analysis?: boolean;
}

export function logUsage(entry: UsageEntry): void {
  const supabase = getSupabase();
  if (!supabase) return;

  supabase.auth.getSession().then(({ data }) => {
    const userId = data.session?.user?.id;
    if (!userId) return;

    supabase
      .from("usage_log")
      .insert({
        user_id: userId,
        model_used: entry.model_used,
        input_tokens: entry.input_tokens,
        output_tokens: entry.output_tokens,
        request_type: entry.request_type,
        deep_analysis: entry.deep_analysis ?? false,
      })
      .then(({ error }) => {
        if (error) console.warn("Usage log failed:", error.message);
      });
  });
}
