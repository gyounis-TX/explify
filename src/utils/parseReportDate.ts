/**
 * Parse a report date string (as returned by the sidecar detect-type endpoint)
 * into a JavaScript Date object.
 *
 * Handles formats like:
 *   - "01/15/2024" or "1/15/2024"
 *   - "01-15-2024" or "1-15-24"
 *   - "January 15, 2024" or "Jan 15, 2024"
 *   - "January 15 2024" (no comma)
 */

const MONTH_NAMES: Record<string, number> = {
  january: 0, jan: 0,
  february: 1, feb: 1,
  march: 2, mar: 2,
  april: 3, apr: 3,
  may: 4,
  june: 5, jun: 5,
  july: 6, jul: 6,
  august: 7, aug: 7,
  september: 8, sep: 8, sept: 8,
  october: 9, oct: 9,
  november: 10, nov: 10,
  december: 11, dec: 11,
};

function expandYear(y: number): number {
  if (y >= 100) return y;
  return y >= 50 ? 1900 + y : 2000 + y;
}

/**
 * Parse a date string from a medical report into a Date object.
 * Returns null if the string cannot be parsed.
 */
export function parseReportDate(dateStr: string | null | undefined): Date | null {
  if (!dateStr) return null;
  const s = dateStr.trim();

  // Try numeric: MM/DD/YYYY or MM-DD-YYYY (with 2 or 4-digit year)
  const numericMatch = s.match(/^(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})$/);
  if (numericMatch) {
    const month = parseInt(numericMatch[1], 10) - 1;
    const day = parseInt(numericMatch[2], 10);
    const year = expandYear(parseInt(numericMatch[3], 10));
    if (month >= 0 && month <= 11 && day >= 1 && day <= 31) {
      return new Date(year, month, day);
    }
  }

  // Try named month: "January 15, 2024" or "Jan 15 2024"
  const namedMatch = s.match(/^([A-Za-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})$/);
  if (namedMatch) {
    const monthIdx = MONTH_NAMES[namedMatch[1].toLowerCase()];
    if (monthIdx !== undefined) {
      const day = parseInt(namedMatch[2], 10);
      const year = parseInt(namedMatch[3], 10);
      if (day >= 1 && day <= 31) {
        return new Date(year, monthIdx, day);
      }
    }
  }

  return null;
}

const SHORT_MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/**
 * Format a report date string for display (e.g., "Jan 15, 2024").
 * Returns null if the date cannot be parsed.
 */
export function formatReportDateShort(dateStr: string | null | undefined): string | null {
  const d = parseReportDate(dateStr);
  if (!d) return null;
  return `${SHORT_MONTHS[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`;
}
