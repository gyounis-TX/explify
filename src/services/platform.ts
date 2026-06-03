/**
 * Platform detection for dual-mode (Tauri desktop / web) operation.
 */

/** True when running inside the Tauri desktop shell. */
export const IS_TAURI = Boolean(
  typeof window !== "undefined" &&
    (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__,
);

/**
 * Base URL for the backend API.
 * - Tauri mode: set dynamically by sidecarApi.initialize() after port discovery.
 * - Web mode: read from VITE_API_URL env var (e.g. "https://api.explify.app").
 */
export const API_BASE_URL: string | undefined = IS_TAURI
  ? undefined // resolved at runtime via invoke("get_sidecar_port")
  : import.meta.env.VITE_API_URL;

/**
 * Application version string.
 * - Tauri mode: populated by Tauri's getVersion() at runtime.
 * - Web mode: injected at build time via VITE_APP_VERSION.
 */
export const APP_VERSION: string =
  import.meta.env.VITE_APP_VERSION ?? "0.0.0";

/** Git short SHA at build time. */
export const GIT_SHA: string = import.meta.env.VITE_GIT_SHA ?? "dev";

/** ISO timestamp of the build. */
export const BUILD_TIME: string = import.meta.env.VITE_BUILD_TIME ?? "";

/**
 * Async extraction (submit + poll) feature flag. Web mode only — the cloud SQS/worker
 * pipeline does not exist in the Tauri desktop sidecar, so this is always false there.
 * Enable by building/serving the web app with VITE_ASYNC_EXTRACTION=true once the
 * backend's ASYNC_EXTRACTION flag and async-extraction stack are deployed.
 */
export const ASYNC_EXTRACTION_ENABLED: boolean =
  !IS_TAURI && import.meta.env.VITE_ASYNC_EXTRACTION === "true";
