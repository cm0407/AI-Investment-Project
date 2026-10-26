import { AppLink } from "@/components/nav/AppLink";
import { Alert, Box, Paper, Stack, Typography } from "@mui/material";

import { loadJson } from "@/lib/data";
import { formatDelta, formatMetric, isUnavailable, outcomeColor } from "@/lib/format";

type Review = {
  reviewDate: string;
  priceAtReview: number | null;
  pctMoveSinceEntry: number | null;
  pctOfHorizonElapsed: number | null;
  assumptionsHeld: string | null;
  assumptionsBroken: string | null;
};

type Prediction = {
  date: string;
  ticker: string;
  entryPrice: number | null;
  targetPrice: number | null;
  horizonMonths: number | null;
  expectedReturnPct: number | null;
  probPositive: number | null;
  probHits20Pct: number | null;
  probLoss: number | null;
  convictionScore: number | null;
  thesisStatus: string;
  notes: string;
  latestReview: Review | null;
};

type Payload = {
  predictions: Prediction[];
  summary: {
    mean: number | null;
    meanExcludingLargest: number | null;
    median: number | null;
    count: number;
    note: string;
  };
};

function Stat({
  label,
  value,
  help,
}: {
  label: string;
  value: number | null;
  help: string;
}) {
  const text = formatDelta(value);
  return (
    <Box sx={{ minWidth: 190 }}>
      <Typography sx={{ fontSize: "0.72rem", color: "text.secondary" }}>{label}</Typography>
      <Typography
        sx={{
          fontFamily: "var(--font-mono)",
          fontVariantNumeric: "tabular-nums",
          fontSize: "1.6rem",
          fontWeight: 600,
          color: outcomeColor(value),
        }}
      >
        {isUnavailable(text) ? "—" : text}
      </Typography>
      <Typography sx={{ fontSize: "0.72rem", color: "text.disabled", maxWidth: 230 }}>
        {help}
      </Typography>
    </Box>
  );
}

function Figure({ label, text }: { label: string; text: string }) {
  return (
    <Box>
      <Typography sx={{ fontSize: "0.68rem", color: "text.secondary" }}>{label}</Typography>
      <Typography
        sx={{
          fontFamily: "var(--font-mono)",
          fontVariantNumeric: "tabular-nums",
          fontSize: "0.88rem",
        }}
      >
        {isUnavailable(text) ? "—" : text}
      </Typography>
    </Box>
  );
}

const pct = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : Math.round(v * 100) + "%";

export default async function PredictionsPage() {
  const data = await loadJson<Payload>("predictions");
  const { summary, predictions } = data;

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto", px: { xs: 2, md: 3 }, py: 4 }}>
      <Typography variant="h1">Every prediction, including the bad ones</Typography>
      <Typography sx={{ color: "text.secondary", mt: 1, mb: 3, maxWidth: 760 }}>
        This page is the scorecard. Each row was written down <em>before</em> the outcome was
        known and has never been edited since — the file behind it only ever gets appended to,
        because a research record you are allowed to tidy up afterwards tells you nothing about
        whether the research was any good.
      </Typography>

      {/* Three averages side by side, because any one of them alone can mislead. */}
      <Paper variant="outlined" sx={{ p: 2.5, mb: 2 }}>
        <Stack direction="row" sx={{ gap: 4, flexWrap: "wrap" }}>
          <Stat
            label="Average move"
            value={summary.mean}
            help="All positions, equally weighted."
          />
          <Stat
            label="Average, best one removed"
            value={summary.meanExcludingLargest}
            help="The same figure without the single largest winner."
          />
          <Stat
            label="Median"
            value={summary.median}
            help="The middle position — unmoved by one outlier at either end."
          />
        </Stack>
        <Alert severity="info" sx={{ mt: 2 }}>
          {summary.note}
        </Alert>
      </Paper>

      <Stack spacing={1.25}>
        {predictions.map((p) => {
          const move = p.latestReview?.pctMoveSinceEntry ?? null;
          const moveText = formatDelta(move);
          const elapsed = p.latestReview?.pctOfHorizonElapsed;
          return (
            <Paper key={p.date + "-" + p.ticker} variant="outlined" sx={{ p: 2 }}>
              <Box
                sx={{
                  display: "flex",
                  gap: 2,
                  alignItems: "baseline",
                  flexWrap: "wrap",
                  mb: 1,
                }}
              >
                <AppLink href={"/stock/" + p.ticker} sx={{ display: "inline-block" }}>
                  <Typography sx={{ fontWeight: 700, fontSize: "1.05rem" }}>
                    {p.ticker}
                  </Typography>
                </AppLink>
                <Typography
                  sx={{
                    fontFamily: "var(--font-mono)",
                    fontVariantNumeric: "tabular-nums",
                    fontSize: "1.05rem",
                    fontWeight: 600,
                    color: outcomeColor(move),
                  }}
                >
                  {isUnavailable(moveText) ? "not yet reviewed" : moveText}
                </Typography>
                <Typography sx={{ fontSize: "0.78rem", color: "text.secondary" }}>
                  predicted {p.date} · {p.thesisStatus}
                </Typography>
              </Box>

              <Stack direction="row" sx={{ gap: 2.5, flexWrap: "wrap", mb: 1 }}>
                <Figure label="Entry" text={formatMetric(p.entryPrice, "usd")} />
                <Figure label="Target" text={formatMetric(p.targetPrice, "usd")} />
                <Figure label="Expected" text={formatDelta(p.expectedReturnPct)} />
                <Figure label="Chance of +20%" text={pct(p.probHits20Pct)} />
                <Figure label="Chance of a loss" text={pct(p.probLoss)} />
                <Figure
                  label="Horizon"
                  text={(p.horizonMonths ?? "—") + " months"}
                />
                <Figure
                  label="Horizon elapsed"
                  text={elapsed === null || elapsed === undefined ? "—" : elapsed.toFixed(0) + "%"}
                />
              </Stack>

              <Typography sx={{ fontSize: "0.82rem", color: "text.secondary" }}>
                {p.notes}
              </Typography>

              {p.latestReview?.assumptionsBroken && (
                <Alert severity="warning" sx={{ mt: 1 }}>
                  Assumption that broke: {p.latestReview.assumptionsBroken}
                </Alert>
              )}

              {/* A move early in a horizon is noise, and saying so is the entire point. */}
              {elapsed !== null && elapsed !== undefined && elapsed < 25 && (
                <Typography sx={{ mt: 0.75, fontSize: "0.72rem", color: "text.disabled" }}>
                  Only {elapsed.toFixed(0)}% of the horizon has passed. At this stage the move
                  is mostly noise, not evidence the thesis was right.
                </Typography>
              )}
            </Paper>
          );
        })}
      </Stack>
    </Box>
  );
}
