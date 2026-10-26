import { AppLink } from "@/components/nav/AppLink";
import { Alert, Box, Paper, Typography } from "@mui/material";

import { CoverageMeter } from "@/components/honesty/CoverageMeter";
import { UnavailableBadge } from "@/components/honesty/UnavailableBadge";
import { loadJson } from "@/lib/data";
import { formatMetric, isUnavailable, type MetricKind } from "@/lib/format";

type Row = {
  ticker: string;
  name: string;
  compositePct: number | null;
  pointsEarned: number | null;
  pointsAvailable: number | null;
  componentsScored: number;
  price: number | null;
  revenueCagrPct: number | null;
  operatingMarginPct: number | null;
  roicPct: number | null;
  peRatio: number | null;
  fcfYieldPct: number | null;
  sectorSpecial: string | null;
};

type Payload = {
  runFile: string;
  wellMeasured: Row[];
  thinlyMeasured: Row[];
  note: string;
};

const COLUMNS: { key: keyof Row; label: string; kind: MetricKind }[] = [
  { key: "price", label: "Price", kind: "usd" },
  { key: "revenueCagrPct", label: "Revenue CAGR", kind: "pct" },
  { key: "operatingMarginPct", label: "Op margin", kind: "pct" },
  { key: "roicPct", label: "ROIC", kind: "pct" },
  { key: "peRatio", label: "P/E", kind: "x" },
  { key: "fcfYieldPct", label: "FCF yield", kind: "pct" },
];

function Table({ rows }: { rows: Row[] }) {
  return (
    <Paper variant="outlined" sx={{ overflowX: "auto", mb: 3 }}>
      <Box component="table" sx={{ width: "100%", borderCollapse: "collapse" }}>
        <Box component="thead">
          <Box component="tr">
            {["Company", "Composite", "Measured", ...COLUMNS.map((c) => c.label)].map(
              (h, i) => (
                <Box
                  key={h}
                  component="th"
                  sx={{
                    textAlign: i <= 2 ? "left" : "right",
                    p: 1.25,
                    fontSize: "0.7rem",
                    color: "text.secondary",
                    fontWeight: 600,
                    whiteSpace: "nowrap",
                    borderBottom: "1px solid",
                    borderColor: "divider",
                  }}
                >
                  {h}
                </Box>
              ),
            )}
          </Box>
        </Box>
        <Box component="tbody">
          {rows.map((r) => (
            <Box
              component="tr"
              key={r.ticker}
              sx={{ "&:hover": { bgcolor: "action.hover" } }}
            >
              <Box component="td" sx={{ p: 1.25, whiteSpace: "nowrap" }}>
                <AppLink href={"/stock/" + r.ticker} sx={{ display: "inline-block" }}>
                  <Typography sx={{ fontWeight: 600, fontSize: "0.9rem" }}>
                    {r.ticker}
                  </Typography>
                </AppLink>
                <Typography sx={{ fontSize: "0.72rem", color: "text.secondary" }}>
                  {r.name}
                  {r.sectorSpecial ? " · " + r.sectorSpecial : ""}
                </Typography>
              </Box>

              {/* Composite is shown with its denominator, never on its own. A company that */}
              {/* can only be scored on 30 available points is not a company scoring 30/100. */}
              <Box component="td" sx={{ p: 1.25, whiteSpace: "nowrap" }}>
                <Typography
                  sx={{
                    fontFamily: "var(--font-mono)",
                    fontVariantNumeric: "tabular-nums",
                    fontWeight: 600,
                  }}
                >
                  {r.compositePct === null ? "—" : r.compositePct.toFixed(1) + "%"}
                </Typography>
                <Typography sx={{ fontSize: "0.68rem", color: "text.disabled" }}>
                  {r.pointsEarned?.toFixed(1)} of {r.pointsAvailable?.toFixed(0)} available
                </Typography>
              </Box>

              <Box component="td" sx={{ p: 1.25 }}>
                <CoverageMeter scored={r.componentsScored} total={16} />
              </Box>

              {COLUMNS.map((c) => {
                const text = formatMetric(r[c.key] as number | null, c.kind);
                return (
                  <Box
                    key={c.key}
                    component="td"
                    sx={{
                      p: 1.25,
                      textAlign: "right",
                      fontFamily: "var(--font-mono)",
                      fontVariantNumeric: "tabular-nums",
                      fontSize: "0.85rem",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {isUnavailable(text) ? <UnavailableBadge compact /> : text}
                  </Box>
                );
              })}
            </Box>
          ))}
        </Box>
      </Box>
    </Paper>
  );
}

export default async function ScreenPage() {
  const data = await loadJson<Payload>("screens-latest");

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto", px: { xs: 2, md: 3 }, py: 4 }}>
      <Typography variant="h1">Latest screen</Typography>
      <Typography sx={{ color: "text.secondary", mt: 1, mb: 3, maxWidth: 780 }}>
        A first pass over a broad universe, ranked on the half of the score a computer can
        check — growth, valuation, balance-sheet strength and cash generation. Nothing here is
        a recommendation. A high rank means &ldquo;worth the reading time&rdquo;, and several
        companies that topped this table were rejected on closer inspection.
      </Typography>
      <Typography sx={{ fontSize: "0.75rem", color: "text.disabled", mb: 2 }}>
        Source: {data.runFile}
      </Typography>

      <Alert severity="info" sx={{ mb: 2 }}>
        A ranking metric is only as good as the figure beside it. Three separate times this
        system put a company at the top of a screen on one strong number — revenue growth,
        a cheap P/E, a jump in profit — while the line next to it said the opposite. The
        coverage meter below is there so a thinly-measured company cannot quietly win on a
        couple of lucky figures.
      </Alert>

      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Well measured — 10 or more of 16 components scored
      </Typography>
      <Table rows={data.wellMeasured} />

      {data.thinlyMeasured.length > 0 && (
        <>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Thinly measured — ranked separately, not mixed in
          </Typography>
          <Alert severity="warning" sx={{ mb: 1.5 }}>
            {data.note}
          </Alert>
          <Table rows={data.thinlyMeasured} />
        </>
      )}
    </Box>
  );
}
