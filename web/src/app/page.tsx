import { AppLink } from "@/components/nav/AppLink";
import { Alert, Box, Paper, Stack, Typography } from "@mui/material";

import { fetchInvestApi } from "@/lib/api";
import { formatDelta, formatMetric, isUnavailable } from "@/lib/format";

export const dynamic = "force-dynamic";

type Company = {
  ticker: string;
  name: string;
  price: number | null;
  marketCap: number | null;
  sectorSpecial: string | null;
};

type PredictionsPayload = {
  predictions: {
    ticker: string;
    thesisStatus: string;
    latestReview: { pctMoveSinceEntry: number | null; pctOfHorizonElapsed: number | null } | null;
  }[];
  summary: {
    mean: number | null;
    meanExcludingLargest: number | null;
    median: number | null;
    count: number;
  };
};

type Digest = { date: string; title: string };

function Headline({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <Box sx={{ minWidth: 170 }}>
      <Typography sx={{ fontSize: "0.72rem", color: "text.secondary" }}>{label}</Typography>
      <Typography
        sx={{
          fontFamily: "var(--font-mono)",
          fontVariantNumeric: "tabular-nums",
          fontSize: "1.5rem",
          fontWeight: 600,
        }}
      >
        {value}
      </Typography>
      <Typography sx={{ fontSize: "0.7rem", color: "text.disabled" }}>{sub}</Typography>
    </Box>
  );
}

export default async function HomePage() {
  const [companies, preds, digests] = await Promise.all([
    fetchInvestApi<Company[]>("/companies"),
    fetchInvestApi<PredictionsPayload>("/predictions"),
    fetchInvestApi<Digest[]>("/digests"),
  ]);

  const reviewed = preds.predictions.filter((p) => p.latestReview?.pctMoveSinceEntry != null);
  const ahead = reviewed.filter((p) => (p.latestReview?.pctMoveSinceEntry ?? 0) > 0).length;
  const maxElapsed = Math.max(
    0,
    ...preds.predictions.map((p) => p.latestReview?.pctOfHorizonElapsed ?? 0),
  );

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto", px: { xs: 2, md: 3 }, py: 5 }}>
      <Typography variant="h1" sx={{ maxWidth: 720 }}>
        Equity research that shows you what it does not know
      </Typography>
      <Typography sx={{ color: "text.secondary", mt: 1.5, mb: 4, maxWidth: 740 }}>
        Every figure here comes from a company&rsquo;s own filings to the SEC, and every row
        names the form and the tag it was taken from. Where a number could not be worked out,
        this site says <em>not available</em> and tells you why, rather than printing a zero —
        which is the single most common way financial dashboards mislead the people reading
        them.
      </Typography>

      {/* ---- the record, first, before any idea ---- */}
      <Paper variant="outlined" sx={{ p: 2.5, mb: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
          The record so far
        </Typography>
        <Stack direction="row" sx={{ gap: 4, flexWrap: "wrap" }}>
          <Headline
            label="Average move"
            value={isUnavailable(formatDelta(preds.summary.mean)) ? "—" : formatDelta(preds.summary.mean)}
            sub="all open predictions"
          />
          <Headline
            label="Best one removed"
            value={
              isUnavailable(formatDelta(preds.summary.meanExcludingLargest))
                ? "—"
                : formatDelta(preds.summary.meanExcludingLargest)
            }
            sub="the same figure, without the top winner"
          />
          <Headline
            label="Median"
            value={isUnavailable(formatDelta(preds.summary.median)) ? "—" : formatDelta(preds.summary.median)}
            sub="the middle position"
          />
          <Headline
            label="Ahead"
            value={ahead + " of " + reviewed.length}
            sub="positions above their entry price"
          />
        </Stack>

        <Alert severity="info" sx={{ mt: 2 }}>
          At most {maxElapsed.toFixed(0)}% of any prediction&rsquo;s horizon has passed. These
          are interim readings on an unfinished experiment, not a track record — a position can
          look right for a year for reasons that have nothing to do with why it was chosen.
        </Alert>

        <AppLink href="/predictions" sx={{ display: "inline-block", mt: 1.5 }}>
          <Typography sx={{ fontSize: "0.85rem", color: "primary.main" }}>
            See every prediction, including the bad ones →
          </Typography>
        </AppLink>
      </Paper>

      {/* ---- what has been analysed ---- */}
      <Typography variant="subtitle2" sx={{ mt: 4, mb: 1 }}>
        Companies analysed ({companies.length})
      </Typography>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr 1fr", sm: "repeat(3, 1fr)", md: "repeat(4, 1fr)" },
          gap: 1,
          mb: 4,
        }}
      >
        {companies.map((c) => (
          <AppLink key={c.ticker} href={"/stock/" + c.ticker}>
            <Paper
              variant="outlined"
              sx={{ p: 1.5, height: "100%", "&:hover": { bgcolor: "action.hover" } }}
            >
            <Typography sx={{ fontWeight: 700, fontSize: "0.92rem" }}>{c.ticker}</Typography>
            <Typography
              sx={{
                fontSize: "0.7rem",
                color: "text.secondary",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {c.name}
            </Typography>
            <Typography
              sx={{
                mt: 0.5,
                fontFamily: "var(--font-mono)",
                fontVariantNumeric: "tabular-nums",
                fontSize: "0.82rem",
              }}
            >
              {isUnavailable(formatMetric(c.price, "usd")) ? "—" : formatMetric(c.price, "usd")}
              </Typography>
            </Paper>
          </AppLink>
        ))}
      </Box>

      {/* ---- how the score is made, because it is half a model ---- */}
      <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          How a score here is made
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary", mb: 1 }}>
          Fifty of the hundred points — growth, valuation, balance-sheet strength, cash
          generation — are arithmetic over SEC filings, and come out the same every time.
        </Typography>
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          The other fifty are judgement: business quality, competitive advantage, catalysts,
          risk and reward, management. Those are written by a language model that is handed the
          finished figures and asked to argue, and its answer is thrown away unless it passes
          seven checks — including one that rejects any number in its reasoning that is not in
          the evidence it was given. Each company page labels which half you are reading and
          shows the full argument behind every point.
        </Typography>
      </Paper>

      {digests[0] && (
        <AppLink href={"/digests/" + digests[0].date}>
          <Paper variant="outlined" sx={{ p: 2 }}>
          <Typography sx={{ fontSize: "0.72rem", color: "text.secondary" }}>
            Latest digest · {digests[0].date}
          </Typography>
            <Typography sx={{ fontWeight: 600 }}>{digests[0].title}</Typography>
          </Paper>
        </AppLink>
      )}
    </Box>
  );
}
