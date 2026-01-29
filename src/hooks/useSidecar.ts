import { useState, useEffect } from "react";
import { sidecarApi } from "../services/sidecarApi";

export function useSidecar() {
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const ready = await sidecarApi.waitForReady();
        if (!cancelled) {
          setIsReady(ready);
          if (!ready) {
            setError("Sidecar failed to start");
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Unknown error");
        }
      }
    }

    init();
    return () => {
      cancelled = true;
    };
  }, []);

  return { isReady, error };
}
