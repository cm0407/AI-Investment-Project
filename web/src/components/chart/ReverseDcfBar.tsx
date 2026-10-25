import { Box, Typography } from "@mui/material";

import { UnavailableBadge } from "@/components/honesty/UnavailableBadge";

/**
 * The most important visual in the app.
 *
 * Two bars answering one question: what growth does today's price already assume, and what
 * has the company actually delivered? A beginner reads it in about a second, and it is the
 * whole investment case for most positions:
 *
 *     McDonald's   price demands 22.4%   ·   delivers 9.2%   → rejected
 *     Intuit       price demands -5.9%   ·   delivers 22.1%  → the market prices decline
 *
 * Colour rule: green when the company out-delivers what the price needs (a low bar to clear),
 * red when the price demands more than the record supports. This is a realised comparison of
 * two measured quantities, which is the only kind of thing this app colours.
 */
export function ReverseDcfBar({
  impliedPct,
  deliveredPct,
}: {
  impliedPct: number | null;
  deliveredPct: number | null;
}) {
  if (impliedPct === null || deliveredPct === null) {
    return (
      <Box>
        <Typography variant="subtitle2" gutterBottom>
          What the price assumes
        </Typography>
        <UnavailableBadge reason="Needs a share price, a share count and positive free cash flow. A reverse DCF on negative cash flow is arithmetic theatre." />
      </Box>
    );
  }

  const scale = Math.max(Math.abs(impliedPct), Math.abs(deliveredPct), 1);
  const clears = deliveredPct >= impliedPct;

  const Row = ({
    label,
    value,
    tone,
  }: {
    label: string;
    value: number;
    tone: "demand" | "delivered";
  }) => (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 0.75 }}>
      <Typography
        sx={{ width: 180, flexShrink: 0, fontSize: "0.8rem", color: "text.secondary" }}
      >
        {label}
      </Typography>
      <Box sx={{ flex: 1, position: "relative", height: 22 }}>
        <Box
          sx={{
            position: "absolute",
            inset: 0,
            bgcolor: "action.hover",
            borderRadius: 0.5,
          }}
        />
        <Box
          sx={{
            position: "absolute",
            top: 0,
            bottom: 0,
            left: value < 0 ? `${50 - (Math.abs(value) / scale) * 50}%` : "50%",
            width: `${(Math.abs(value) / scale) * 50}%`,
            bgcolor:
              tone === "demand"
                ? clears
                  ? "action.selected"
                  : "error.main"
                : clears
                  ? "success.main"
                  : "action.selected",
            borderRadius: 0.5,
            transition: "width 200ms ease",
          }}
        />
        {/* zero line — matters because an implied rate can be negative */}
        <Box
          sx={{
            position: "absolute",
            left: "50%",
            top: -2,
            bottom: -2,
            width: "1px",
            bgcolor: "divider",
          }}
        />
      </Box>
      <Typography
        sx={{
          width: 72,
          textAlign: "right",
          fontFamily: "var(--font-mono)",
          fontVariantNumeric: "tabular-nums",
          fontSize: "0.85rem",
          fontWeight: 600,
        }}
      >
        {value.toFixed(1)}%
      </Typography>
    </Box>
  );

  return (
    <Box>
      <Typography variant="subtitle2" gutterBottom>
        What the price assumes, against what the company delivers
      </Typography>
      <Row label="Price requires" value={impliedPct} tone="demand" />
      <Row label="Company delivered" value={deliveredPct} tone="delivered" />
      <Typography
        sx={{ mt: 1, fontSize: "0.78rem", color: clears ? "success.main" : "error.main" }}
      >
        {clears
          ? `The bar is low: the company has delivered ${(deliveredPct - impliedPct).toFixed(1)} points more growth than the price needs.`
          : `The price demands ${(impliedPct - deliveredPct).toFixed(1)} points more growth per year than the company has delivered.`}
      </Typography>
      <Typography sx={{ mt: 0.5, fontSize: "0.72rem", color: "text.disabled" }}>
        Annual free-cash-flow growth, 10-year window, 10% required return. A projection under
        stated assumptions — not a forecast.
      </Typography>
    </Box>
  );
}
