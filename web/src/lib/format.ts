/**
 * The ONE place a number becomes text.
 *
 * This file exists because of a single rule that the whole product rests on:
 *
 *     A metric that could not be measured is NOT zero.
 *
 * The Python pipeline goes to real trouble to keep those apart — it suppresses a total when
 * one component is missing rather than summing what's left, it refuses to treat an abandoned
 * XBRL tag's last value as current, and it reports `null` where a bank has no gross profit.
 * All of that care is destroyed the moment a component renders `{value}` and React prints
 * nothing, or `{value ?? 0}` and React prints a lie.
 *
 * So formatting is centralised. `formatMetric(null)` returns a sentinel the UI must render
 * as an explicit "Not available" chip — never an empty cell, never a dash, never 0.
 */

export const UNAVAILABLE = "__UNAVAILABLE__" as const;

export type MetricKind = "pct" | "usd" | "x" | "ratio" | "num" | "shares";

/**
 * Returns either a formatted string or the UNAVAILABLE sentinel.
 * Callers MUST branch on the sentinel and render <UnavailableBadge/>.
 */
export function formatMetric(
  value: number | null | undefined,
  kind: MetricKind = "num",
  decimals = 1,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return UNAVAILABLE;
  }

  switch (kind) {
    case "pct":
      return `${value.toFixed(decimals)}%`;
    case "x":
      return `${value.toFixed(decimals)}×`;
    case "ratio":
      return value.toFixed(2);
    case "shares":
      return compact(value, 1);
    case "usd":
      return `$${compact(value, 2)}`;
    default:
      return value.toLocaleString(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
  }
}

function compact(value: number, decimals: number): string {
  const abs = Math.abs(value);
  const units: [number, string][] = [
    [1e12, "T"],
    [1e9, "B"],
    [1e6, "M"],
    [1e3, "K"],
  ];
  for (const [cutoff, suffix] of units) {
    if (abs >= cutoff) return `${(value / cutoff).toFixed(decimals)}${suffix}`;
  }
  return value.toFixed(decimals);
}

/** Signed, for anything compared against a benchmark or an entry price. */
export function formatDelta(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return UNAVAILABLE;
  return `${value >= 0 ? "+" : ""}${value.toFixed(decimals)}%`;
}

export function isUnavailable(formatted: string): boolean {
  return formatted === UNAVAILABLE;
}

/**
 * Colour is reserved for REALISED outcomes measured against something.
 *
 * Deliberately NOT applied to scores. A 79 is not "green" — it is 79. Colouring quality
 * judgements trains the eye to read a score as an instruction, which is exactly what this
 * project refuses to do.
 */
export function outcomeColor(
  value: number | null | undefined,
): "success.main" | "error.main" | "text.secondary" {
  if (value === null || value === undefined || Number.isNaN(value)) return "text.secondary";
  if (value > 0) return "success.main";
  if (value < 0) return "error.main";
  return "text.secondary";
}
