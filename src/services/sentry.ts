import * as Sentry from "@sentry/react";

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN ?? "";

/** PHI patterns to scrub from error reports (HIPAA Safe Harbor identifiers). */
const PHI_PATTERNS = [
  /\b\d{3}-\d{2}-\d{4}\b/g,                    // SSN
  /\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b/g,        // dates (DOB, etc.)
  /\b[A-Z]{1,2}\d{6,10}\b/g,                    // MRN patterns
  /\b\d{10}\b/g,                                 // phone numbers
  /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/gi, // email
  /https?:\/\/[^\s<>"']+|www\.[^\s<>"']+/g,     // URLs
  /(?:patient|name)\s*[:=]\s*[^\n,;]{2,40}/gi,  // labeled patient name
  /(?:age[d:]?\s*)?(?:9[0-9]|1[0-4][0-9])\s*(?:-?\s*)?(?:year|yr|y\/?o|y\.o\.)/gi, // age>89
  /(?:date of (?:study|exam|service|procedure|admission|discharge|report|visit|birth))\s*[:=]?\s*[^\n]{1,30}/gi, // labeled dates
];

function scrubPhi(str: string): string {
  let result = str;
  for (const pattern of PHI_PATTERNS) {
    result = result.replace(pattern, "[REDACTED]");
  }
  return result;
}

function scrubEventData(obj: unknown): unknown {
  if (typeof obj === "string") return scrubPhi(obj);
  if (Array.isArray(obj)) return obj.map(scrubEventData);
  if (obj && typeof obj === "object") {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj)) {
      result[key] = scrubEventData(value);
    }
    return result;
  }
  return obj;
}

export function initSentry(): void {
  if (!SENTRY_DSN) return;

  Sentry.init({
    dsn: SENTRY_DSN,
    environment: import.meta.env.MODE ?? "development",
    beforeSend(event) {
      // Scrub PHI from exception messages
      if (event.exception?.values) {
        for (const ex of event.exception.values) {
          if (ex.value) ex.value = scrubPhi(ex.value);
        }
      }
      // Scrub breadcrumb messages
      if (event.breadcrumbs) {
        for (const bc of event.breadcrumbs) {
          if (bc.message) bc.message = scrubPhi(bc.message);
          if (bc.data) bc.data = scrubEventData(bc.data) as Record<string, unknown>;
        }
      }
      // Scrub extra context
      if (event.extra) {
        event.extra = scrubEventData(event.extra) as Record<string, unknown>;
      }
      return event;
    },
  });
}

export function captureException(
  error: Error,
  context?: Record<string, unknown>,
): void {
  if (!SENTRY_DSN) return;
  Sentry.captureException(error, { extra: context });
}

export function captureMessage(message: string, level: "info" | "warning" | "error" = "info"): void {
  if (!SENTRY_DSN) return;
  Sentry.captureMessage(scrubPhi(message), level);
}
