import { sidecarApi } from "./sidecarApi";
import { IS_TAURI } from "./platform";

interface UsageEntry {
  model_used: string;
  input_tokens: number;
  output_tokens: number;
  request_type: "explain" | "letter" | "synthesize";
  deep_analysis?: boolean;
}

export function logUsage(entry: UsageEntry): void {
  if (IS_TAURI) return; // Desktop mode: no usage tracking

  // Fire-and-forget POST to sidecar usage log endpoint
  sidecarApi
    .logUsage(entry)
    .catch((err) => console.warn("Usage log failed:", err));
}
