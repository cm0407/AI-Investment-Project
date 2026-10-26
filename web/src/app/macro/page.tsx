import { Box, Paper, Stack, Typography } from "@mui/material";

import { loadJson } from "@/lib/data";
import { outcomeColor } from "@/lib/format";

type Series = {
  id: string;
  description: string;
  latest: number | null;
  latestDate: string | null;
  prior: number | null;
  change: number | null;
};

type Payload = { retrievedAt: string; series: Series[] };

export default async function MacroPage() {
  const data = await loadJson<Payload>("macro");

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto", px: { xs: 2, md: 3 }, py: 4 }}>
      <Typography variant="h1">The weather</Typography>
      <Typography sx={{ color: "text.secondary", mt: 1, mb: 3, maxWidth: 780 }}>
        Background conditions, not signals. These numbers are here because a company&rsquo;s
        worth depends on what safe money pays — when the 10-year Treasury yield rises, every
        future dollar a business will earn is worth a little less today, and every valuation on
        this site shifts with it. None of these series is a reason to buy or sell anything.
      </Typography>

      <Stack spacing={1.25}>
        {data.series.map((s) => (
          <Paper key={s.id} variant="outlined" sx={{ p: 2 }}>
            <Box
              sx={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "baseline",
                gap: 2,
                flexWrap: "wrap",
              }}
            >
              <Box>
                <Typography sx={{ fontWeight: 600 }}>{s.description}</Typography>
                <Typography sx={{ fontSize: "0.72rem", color: "text.disabled" }}>
                  FRED series {s.id} · as of {s.latestDate ?? "unknown"}
                </Typography>
              </Box>
              <Box sx={{ textAlign: "right" }}>
                <Typography
                  sx={{
                    fontFamily: "var(--font-mono)",
                    fontVariantNumeric: "tabular-nums",
                    fontSize: "1.5rem",
                    fontWeight: 600,
                  }}
                >
                  {s.latest === null ? "—" : s.latest.toFixed(2)}
                </Typography>
                {/* A change against the prior reading is a realised move, so it gets colour. */}
                <Typography
                  sx={{
                    fontFamily: "var(--font-mono)",
                    fontVariantNumeric: "tabular-nums",
                    fontSize: "0.8rem",
                    color: outcomeColor(s.change),
                  }}
                >
                  {s.change === null
                    ? "—"
                    : (s.change >= 0 ? "+" : "") + s.change.toFixed(2) + " vs prior"}
                </Typography>
              </Box>
            </Box>
          </Paper>
        ))}
      </Stack>

      <Typography sx={{ mt: 3, fontSize: "0.72rem", color: "text.disabled" }}>
        Retrieved {data.retrievedAt} from the Federal Reserve Bank of St. Louis (FRED). Colour
        marks direction against the previous reading only — it does not mean good or bad.
      </Typography>
    </Box>
  );
}
