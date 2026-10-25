import { Box, Tooltip, Typography } from "@mui/material";

import { CoverageMeter } from "@/components/honesty/CoverageMeter";

/**
 * A score, and immediately beside it how much of the score was actually measurable.
 *
 * Two things this deliberately does NOT do:
 *
 * 1. It does not colour the score. A 79 is not "green". Colouring a quality judgement trains
 *    the eye to read it as an instruction, and this system's whole point is that a score is
 *    an argument you can inspect, not a recommendation.
 *
 * 2. It does not hide the denominator. JPMorgan scores 20.5 out of 30 AVAILABLE points,
 *    because two pillars are meaningless for a bank. Rendering "20.5/100" would make a
 *    correctly-analysed bank look like a failing company.
 */
export function ScoreGauge({
  total,
  band,
  pointsEarned,
  pointsAvailable,
  pointsPossible = 50,
  componentsScored,
  componentsTotal = 16,
  judgmentSource,
}: {
  total: number | null;
  band: string;
  pointsEarned: number | null;
  pointsAvailable: number | null;
  pointsPossible?: number;
  componentsScored: number;
  componentsTotal?: number;
  judgmentSource?: "model" | "analyst" | null;
}) {
  const pct =
    total !== null && Number.isFinite(total) ? Math.max(0, Math.min(100, total)) : 0;
  const capped = pointsAvailable !== null && pointsAvailable < pointsPossible;

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "baseline", gap: 1.5, flexWrap: "wrap" }}>
        <Typography
          sx={{
            fontFamily: "var(--font-mono)",
            fontVariantNumeric: "tabular-nums",
            fontSize: "2.4rem",
            lineHeight: 1,
            fontWeight: 600,
          }}
        >
          {total === null ? "—" : total.toFixed(1)}
        </Typography>
        <Typography sx={{ color: "text.secondary", fontSize: "0.95rem" }}>/ 100</Typography>
        <Typography
          sx={{
            ml: 0.5,
            px: 1,
            py: 0.25,
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 0.5,
            fontSize: "0.72rem",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            color: "text.secondary",
          }}
        >
          {band}
        </Typography>
      </Box>

      {/* neutral ramp — deliberately not a traffic light */}
      <Box
        sx={{
          mt: 1.25,
          height: 8,
          borderRadius: 1,
          bgcolor: "action.hover",
          overflow: "hidden",
        }}
      >
        <Box
          sx={{
            width: `${pct}%`,
            height: "100%",
            bgcolor: "text.primary",
            opacity: 0.75,
            transition: "width 250ms ease",
          }}
        />
      </Box>

      <Box
        sx={{
          mt: 1,
          display: "flex",
          alignItems: "center",
          gap: 2,
          flexWrap: "wrap",
        }}
      >
        <CoverageMeter scored={componentsScored} total={componentsTotal} />

        {capped && (
          <Tooltip
            arrow
            title="Some scoring pillars are meaningless for this company's industry, so the maximum obtainable score is lower. The company is not being marked down for it."
          >
            <Typography
              sx={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.72rem",
                color: "warning.main",
                cursor: "help",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {pointsEarned?.toFixed(1)} of {pointsAvailable?.toFixed(0)} available
              {" "}(not {pointsPossible})
            </Typography>
          </Tooltip>
        )}

        {judgmentSource && (
          <Tooltip
            arrow
            title={
              judgmentSource === "model"
                ? "The five judgment pillars were scored by a model, whose output passed seven validation checks including a groundedness test. Its written reasoning is shown below."
                : "The five judgment pillars were written by a person."
            }
          >
            <Typography
              sx={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.72rem",
                color: "text.secondary",
                cursor: "help",
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 0.5,
                px: 0.75,
              }}
            >
              judgment: {judgmentSource}
            </Typography>
          </Tooltip>
        )}
      </Box>
    </Box>
  );
}
