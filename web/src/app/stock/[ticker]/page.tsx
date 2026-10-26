import { Alert, Box, Divider, Paper, Stack, Typography } from "@mui/material";

import { ReverseDcfBar } from "@/components/chart/ReverseDcfBar";
import { CoverageMeter } from "@/components/honesty/CoverageMeter";
import { UnavailableBadge } from "@/components/honesty/UnavailableBadge";
import { ScoreGauge } from "@/components/score/ScoreGauge";
import { loadJson, loadJsonOrNull } from "@/lib/data";
import { formatMetric, isUnavailable, type MetricKind } from "@/lib/format";

/** Every analysed company becomes its own HTML file at build time. */
export async function generateStaticParams() {
  const companies = await loadJson<{ ticker: string }[]>("companies");
  return companies.map((c) => ({ ticker: c.ticker }));
}

type Caveat = {
  kind: string;
  severity: "info" | "warning" | "critical";
  message: string;
  affectedMetrics: string[];
};

type Company = {
  ticker: string;
  name: string;
  cik: string;
  sicDescription: string;
  sectorSpecial: string | null;
  metrics: Record<string, number | null>;
  _unavailable: Record<string, string>;
  financials: {
    periodEnd: string;
    revenue: number | null;
    operatingIncome: number | null;
    netIncome: number | null;
    sourceTag?: string;
    sourceForm?: string;
    sourceAccession?: string;
  }[];
  caveats: Caveat[];
};

type Thesis = {
  total: number | null;
  band: string;
  dataPointsEarned: number | null;
  dataPointsAvailable: number | null;
  componentsScored: number;
  componentsTotal: number;
  judgmentSource: "model" | "analyst" | null;
  dataScoredAt: string | null;
  judgmentAt: string | null;
  freshnessWarning: string | null;
  judgmentPillars: {
    name: string;
    points: number | null;
    justification: string | null;
    source: string;
    modelRun: { at: string; validationsPassed: string[]; attempts: number } | null;
  }[];
  unscorablePillars: string[];
};

/** A metric cell that can never silently render a null as zero. */
function Metric({
  label,
  value,
  reason,
  kind = "num",
}: {
  label: string;
  value: number | null;
  reason?: string;
  kind?: MetricKind;
}) {
  const text = formatMetric(value, kind);
  return (
    <Box sx={{ minWidth: 140 }}>
      <Typography sx={{ fontSize: "0.72rem", color: "text.secondary", mb: 0.25 }}>
        {label}
      </Typography>
      {isUnavailable(text) ? (
        <UnavailableBadge reason={reason} />
      ) : (
        <Typography
          sx={{
            fontFamily: "var(--font-mono)",
            fontVariantNumeric: "tabular-nums",
            fontSize: "1rem",
            fontWeight: 600,
          }}
        >
          {text}
        </Typography>
      )}
    </Box>
  );
}

export default async function StockPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;

  const tk = ticker.toUpperCase();
  const [company, thesis] = await Promise.all([
    loadJson<Company>("company-" + tk),
    // A company can be analysed without ever being scored. That is a real state, so the
    // page renders without a thesis block rather than failing.
    loadJsonOrNull<Thesis>("thesis-" + tk),
  ]);

  const m = company.metrics;
  const why = (k: string) => company._unavailable[k];
  const critical = company.caveats.filter((c) => c.severity === "critical");
  const other = company.caveats.filter((c) => c.severity !== "critical");

  return (
    <Box sx={{ maxWidth: 1100, mx: "auto", px: { xs: 2, md: 3 }, py: 4 }}>
      {/* ---- identity ---- */}
      <Typography variant="h1">{company.name}</Typography>
      <Typography sx={{ color: "text.secondary", mb: 2 }}>
        {company.ticker} · CIK {company.cik} · {company.sicDescription}
        {company.sectorSpecial ? ` · ${company.sectorSpecial}` : ""}
      </Typography>

      {/* ---- critical caveats go ABOVE everything, never in a collapsed panel ---- */}
      {critical.map((c, i) => (
        <Alert key={i} severity="error" sx={{ mb: 2 }}>
          {c.message}
        </Alert>
      ))}

      {company.sectorSpecial && (
        <Alert severity="info" sx={{ mb: 2 }}>
          This is a <strong>{company.sectorSpecial}</strong> company. Several standard ratios
          do not transfer to this industry and are shown as unavailable rather than
          misapplied — a bank borrowing ten times its equity is doing banking, not failing.
        </Alert>
      )}

      {/* A total built from two halves measured weeks apart is not one number. This
          belongs above the score, not in a footnote under it. */}
      {thesis?.freshnessWarning && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {thesis.freshnessWarning}
        </Alert>
      )}

      {/* ---- score ---- */}
      {thesis && (
        <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
          <ScoreGauge
            total={thesis.total}
            band={thesis.band}
            pointsEarned={thesis.dataPointsEarned}
            pointsAvailable={thesis.dataPointsAvailable}
            componentsScored={thesis.componentsScored}
            componentsTotal={thesis.componentsTotal}
            judgmentSource={thesis.judgmentSource}
          />
          {thesis.dataScoredAt && (
            <Typography sx={{ mt: 1, fontSize: "0.7rem", color: "text.disabled" }}>
              Data pillars scored {thesis.dataScoredAt.slice(0, 10)}
              {thesis.judgmentAt
                ? " · judgment pillars " + thesis.judgmentAt.slice(0, 10)
                : ""}
            </Typography>
          )}
          {thesis.unscorablePillars.length > 0 && (
            <Box sx={{ mt: 1.5 }}>
              {thesis.unscorablePillars.map((u, i) => (
                <Typography key={i} sx={{ fontSize: "0.76rem", color: "warning.main" }}>
                  Not scored — {u}
                </Typography>
              ))}
            </Box>
          )}
        </Paper>
      )}

      {/* ---- the headline comparison ---- */}
      <Paper variant="outlined" sx={{ p: 2.5, mb: 3 }}>
        <ReverseDcfBar
          impliedPct={m.reverse_dcf_implied_growth_pct ?? null}
          deliveredPct={m.fcf_cagr_pct ?? null}
        />
      </Paper>

      {/* ---- metrics ---- */}
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Valuation
      </Typography>
      <Stack direction="row" sx={{ gap: 3, flexWrap: "wrap", mb: 3 }}>
        <Metric label="Price" value={m.price} reason={why("price")} kind="usd" />
        <Metric label="Market cap" value={m.market_cap} reason={why("market_cap")} kind="usd" />
        <Metric label="P/E" value={m.pe_ratio} reason={why("pe_ratio")} kind="x" />
        <Metric label="P/FCF" value={m.pfcf_ratio} reason={why("pfcf_ratio")} kind="x" />
        <Metric label="EV/EBITDA" value={m.ev_ebitda} reason={why("ev_ebitda")} kind="x" />
        <Metric
          label="FCF yield"
          value={m.fcf_yield_pct}
          reason={why("fcf_yield_pct")}
          kind="pct"
        />
      </Stack>

      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        Quality
      </Typography>
      <Stack direction="row" sx={{ gap: 3, flexWrap: "wrap", mb: 3 }}>
        <Metric
          label="Operating margin"
          value={m.operating_margin_pct}
          reason={why("operating_margin_pct")}
          kind="pct"
        />
        <Metric
          label="FCF margin"
          value={m.fcf_margin_pct}
          reason={why("fcf_margin_pct")}
          kind="pct"
        />
        <Metric label="ROIC" value={m.roic_pct} reason={why("roic_pct")} kind="pct" />
        <Metric
          label="Debt / equity"
          value={m.debt_to_equity}
          reason={why("debt_to_equity")}
          kind="x"
        />
        <Metric
          label="Share count change"
          value={m.share_count_change_pct}
          reason={why("share_count_change_pct")}
          kind="pct"
        />
      </Stack>

      {/* ---- financials, with provenance on every row ---- */}
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        As reported to the SEC
      </Typography>
      <Paper variant="outlined" sx={{ mb: 3, overflowX: "auto" }}>
        <Box component="table" sx={{ width: "100%", borderCollapse: "collapse" }}>
          <Box component="thead">
            <Box component="tr">
              {["Period", "Revenue", "Operating income", "Net income", "Source"].map((h) => (
                <Box
                  key={h}
                  component="th"
                  sx={{
                    textAlign: h === "Period" || h === "Source" ? "left" : "right",
                    p: 1.25,
                    fontSize: "0.72rem",
                    color: "text.secondary",
                    borderBottom: "1px solid",
                    borderColor: "divider",
                    whiteSpace: "nowrap",
                  }}
                >
                  {h}
                </Box>
              ))}
            </Box>
          </Box>
          <Box component="tbody">
            {company.financials.map((f) => (
              <Box component="tr" key={f.periodEnd}>
                <Box component="td" sx={{ p: 1.25, fontFamily: "var(--font-mono)" }}>
                  {f.periodEnd}
                </Box>
                {[f.revenue, f.operatingIncome, f.netIncome].map((v, i) => {
                  const text = formatMetric(v, "usd");
                  return (
                    <Box
                      key={i}
                      component="td"
                      sx={{
                        p: 1.25,
                        textAlign: "right",
                        fontFamily: "var(--font-mono)",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {isUnavailable(text) ? <UnavailableBadge /> : text}
                    </Box>
                  );
                })}
                <Box
                  component="td"
                  sx={{ p: 1.25, fontSize: "0.68rem", color: "text.disabled" }}
                >
                  {f.sourceForm} · {f.sourceTag}
                </Box>
              </Box>
            ))}
          </Box>
        </Box>
      </Paper>

      {/* ---- judgment pillars, with their reasoning in full ---- */}
      {thesis && thesis.judgmentPillars.length > 0 && (
        <>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Judgment — scored by {thesis.judgmentSource}
          </Typography>
          <Stack spacing={1.5} sx={{ mb: 3 }}>
            {thesis.judgmentPillars.map((p) => (
              <Paper key={p.name} variant="outlined" sx={{ p: 2 }}>
                <Box
                  sx={{ display: "flex", justifyContent: "space-between", gap: 2, mb: 0.75 }}
                >
                  <Typography sx={{ fontWeight: 600, textTransform: "capitalize" }}>
                    {p.name.replace(/_/g, " ")}
                  </Typography>
                  <Typography
                    sx={{
                      fontFamily: "var(--font-mono)",
                      fontVariantNumeric: "tabular-nums",
                      fontWeight: 600,
                    }}
                  >
                    {p.points ?? "—"}
                  </Typography>
                </Box>
                <Typography sx={{ fontSize: "0.86rem", color: "text.secondary" }}>
                  {p.justification ?? "No justification recorded."}
                </Typography>
                {p.modelRun && (
                  <Typography sx={{ mt: 1, fontSize: "0.68rem", color: "text.disabled" }}>
                    Written by a model · {p.modelRun.validationsPassed.length} validation
                    checks passed · attempt {p.modelRun.attempts} · {p.modelRun.at}
                  </Typography>
                )}
              </Paper>
            ))}
          </Stack>
        </>
      )}

      {/* ---- remaining caveats ---- */}
      {other.length > 0 && (
        <>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>
            Data cautions
          </Typography>
          <Stack spacing={1} sx={{ mb: 3 }}>
            {other.map((c, i) => (
              <Alert key={i} severity={c.severity === "warning" ? "warning" : "info"}>
                {c.message}
              </Alert>
            ))}
          </Stack>
        </>
      )}

      <Divider sx={{ my: 3 }} />
      <Typography sx={{ fontSize: "0.72rem", color: "text.disabled" }}>
        Research and education, not financial advice. Claude is not a licensed financial
        advisor and no return is guaranteed. Figures come from SEC EDGAR filings; every row
        above names the form and XBRL tag it was taken from. Forward-looking figures are
        projections under stated assumptions, not forecasts.
      </Typography>
    </Box>
  );
}
