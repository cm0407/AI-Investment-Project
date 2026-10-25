import { Box, Tooltip } from "@mui/material";

/**
 * Sixteen dots. Filled ones were measured.
 *
 * A score of 93.5% once topped a screen on SIX of sixteen components while an 81.5% was
 * scored on fifteen. Printed as bare percentages those look like a clear ranking; they are
 * not comparable at all. The dots make the size of the evidence base visible at a glance,
 * so a high percentage on thin coverage LOOKS thin.
 *
 * Rule: never render a score without this beside it.
 */
export function CoverageMeter({
  scored,
  total = 16,
  showLabel = true,
}: {
  scored: number;
  total?: number;
  showLabel?: boolean;
}) {
  const thin = scored < 10;
  return (
    <Tooltip
      arrow
      title={
        `Scored on ${scored} of ${total} components.` +
        (thin
          ? " Fewer than 10 — this score rests on a thin evidence base and is NOT comparable with a well-measured company."
          : "")
      }
    >
      <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, cursor: "help" }}>
        <Box sx={{ display: "inline-flex", gap: "2px" }}>
          {Array.from({ length: total }, (_, i) => (
            <Box
              key={i}
              sx={{
                width: 5,
                height: 5,
                borderRadius: "50%",
                bgcolor:
                  i < scored
                    ? thin
                      ? "warning.main"
                      : "text.primary"
                    : "action.disabledBackground",
              }}
            />
          ))}
        </Box>
        {showLabel && (
          <Box
            component="span"
            sx={{
              fontFamily: "var(--font-mono)",
              fontSize: "0.72rem",
              color: thin ? "warning.main" : "text.secondary",
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {scored}/{total}
          </Box>
        )}
      </Box>
    </Tooltip>
  );
}
