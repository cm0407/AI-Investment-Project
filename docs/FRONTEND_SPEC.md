# INVEST Frontend — Build Specification

**A brief to hand to Claude Code.** Drop this into a new, empty repository and point Claude
Code at it.

**Scope note:** this specifies a **new** application. It deliberately reuses the stack and
conventions from `TCSS_460/Frontend/group-project-frontend-public-group-2` because those are
proven and familiar — but it does not modify that repository, which is graded coursework.

---

## 1. What this app is

A research terminal for a **beginner investor**, backed by a Python system that analyses U.S.
stocks from SEC filings.

**The product thesis, and the thing that must survive every design decision:**

> Every other stock app shows you a number. This one shows you how much of the number is
> actually known.

The backing system is built to refuse to guess. It reports `DATA UNAVAILABLE OR UNVERIFIED`
rather than zero, records which XBRL tag produced each figure, tracks how many of 16 scoring
components had usable data, and keeps an append-only record of every prediction including the
wrong ones. **The UI's job is to make that visible, not to hide it behind a clean dashboard.**

Concretely, the app must be able to show a user:

- "This company scores 20.5 out of **30 available** points — 20 points could not be scored
  because it's a bank and those ratios are meaningless for banks."
- "Operating income came from a *pre-tax income* tag because this company stopped reporting
  the preferred one in 2014, which overstates the margin."
- "This 15.5% growth rate is measured from the 2020 oil crash. The recent three-year rate is
  **−4.2%**."
- "I predicted this would rise 18%. It rose 51%, because it got acquired, and I had explicitly
  said the upside was capped. Here is what I got wrong."

If a design choice would make any of those harder to show, it is the wrong choice.

**Hard constraint — this is research, not advice.** A disclaimer must be present on every page
that displays a score, target or scenario. No "Buy" buttons. No brokerage integration. The
backing system's own rules forbid implying certainty, and the UI must not undo that.

---

## 2. Architecture

```
┌─────────────────────┐      HTTPS/JSON      ┌──────────────────────┐
│  Next.js frontend   │ ───────────────────▶ │  FastAPI service     │
│  (this repo)        │                      │  (INVEST/api/)       │
└─────────────────────┘                      └──────────┬───────────┘
                                                        │ imports
                                             ┌──────────▼───────────┐
                                             │  invest/ package     │
                                             │  + data/ + memory/   │
                                             └──────────────────────┘
```

This mirrors the TCSS 460 two-team split (frontend ↔ Group 1's API) exactly. **The frontend
contains no analysis logic.** Never recompute a metric client-side — if a number is needed,
the API provides it, because only the API knows whether it is trustworthy.

**The API does not exist yet.** See `INVEST/docs/PLATFORM_ROADMAP.md` Priority 1. Build the
frontend against mocked responses matching §5 until it does.

---

## 3. Tech stack

Carried over from the TCSS 460 project — proven, and the conventions are already written down.

| Layer | Choice | Why |
|---|---|---|
| Framework | **Next.js 16 (App Router)** | Server Components fetch on the server; no API keys in the browser |
| Language | **TypeScript 5**, strict | Non-negotiable given the data contracts |
| UI | **MUI v9** + Emotion | Already know it; dense data tables are its strength |
| Charts | **Recharts** | Composable, works with MUI theming, SSR-friendly |
| Tables | **TanStack Table v8** (headless) | Screen results need sorting/filtering/virtualisation; headless keeps MUI styling |
| Auth | **NextAuth v5** | Same pattern as the course project |
| Fetching | Server Components + Server Actions | No client data library needed for a read-mostly app |
| Types | **openapi-typescript** generating from FastAPI's schema | Stops the type drift the course project hit |

**Deliberately NOT included:** Redux/Zustand (Server Components handle this), tRPC (the API is
Python), Tailwind (MUI's `sx` is the single styling system — the course project installed
Tailwind and never used it; don't repeat that).

```bash
npx create-next-app@latest invest-frontend --typescript --app --no-tailwind
npm i @mui/material @mui/material-nextjs @mui/icons-material @emotion/react @emotion/styled @emotion/cache
npm i recharts @tanstack/react-table next-auth@beta
npm i -D openapi-typescript
```

---

## 4. File structure

```
src/
  app/
    layout.tsx                  Header + Footer once; providers
    providers.tsx               AppRouterCacheProvider → ThemeProvider → CssBaseline → SessionProvider
    page.tsx                    Dashboard
    screen/page.tsx             Screener results, filterable
    stock/[ticker]/
      page.tsx                  Company deep-dive
      loading.tsx
      error.tsx
    predictions/page.tsx        Track record + calibration  ← the differentiator
    digests/
      page.tsx                  Archive
      [date]/page.tsx           One digest
    macro/page.tsx              Economic backdrop
    preferences/page.tsx        Risk profile (gates recommendations)
    api/auth/[...nextauth]/route.ts
  components/
    index.ts                    Barrel — import everything from "@/components"
    layout/        Header, Footer, PageContainer, PageTitle, SectionHeading
    data/          MetricTile, MetricGrid, DataTable, FinancialsTable, ProvenanceTooltip
    honesty/       UnavailableBadge, CoverageMeter, CaveatList, SectorWarning, StaleDataChip
    score/         ScoreGauge, PillarBreakdown, JudgmentCard
    scenario/      ScenarioBars, ProbabilityStrip, RangeWidthWarning
    chart/         RevenueChart, MarginChart, PriceChart, BenchmarkChart
    prediction/    PredictionRow, OutcomeBadge, CalibrationChart
    feedback/      EmptyState, LoadingState, ErrorState, CardSkeleton
  lib/
    api.ts                      fetchInvestApi — ALL calls go through here
    actions/                    Server Actions returning ActionResult<T>
    format.ts                   formatMetric — the ONE place null → "Not available"
  types/
    generated.ts                openapi-typescript output — never hand-edit
    invest.ts                   Hand-written view models that wrap generated types
  theme.ts                      Single source of truth for visual decisions
```

**Conventions inherited from the course project — keep all of them:**

- All API calls go through `fetchInvestApi`; never a raw `fetch`
- Writes go through Server Actions returning `ActionResult<T>` (`{ok:true,data}` | `{ok:false,error}`)
- `src/theme.ts` is the only place colours and spacing are decided; use `sx`, never `style={{}}`
- Shared components live in `src/components/` and are re-exported from the barrel
- `<Header/>`/`<Footer/>` render once in `layout.tsx`
- Every page wrapped in `<PageContainer>`
- Pages fetching live data: `export const dynamic = "force-dynamic"`
- `<Button component={Link}>` throws in a Server Component — use `<ButtonLink>`

---

## 5. Data contracts

Generate `src/types/generated.ts` from the FastAPI OpenAPI schema. These are the shapes the
UI must handle.

### The invariant that matters most

```ts
// A metric is a VALUE or a REASON IT IS ABSENT. Never a bare number.
type Metric = {
  value: number | null;
  unit: "pct" | "usd" | "x" | "ratio";
  unavailableReason?: string;   // present iff value === null
  unreliableForSector?: string; // computed, but meaningless for this industry
  sourceTag?: string;           // e.g. "us-gaap:OperatingIncomeLoss"
  sourceForm?: string;          // "10-K"
  sourceAccession?: string;     // traceable to the filing
  periodEnd?: string;
  isFallbackTag?: boolean;      // the preferred tag was unavailable
  fallbackCaution?: string;
};
```

**`value: null` must render as "Not available" with the reason on hover. It must never render
as 0, "—" alone, or an empty cell.** This is the product.

### Core responses

```ts
type Company = {
  ticker: string; name: string; cik: string;
  sic: string; sicDescription: string;
  sectorSpecial: string | null;          // "banking/credit" etc.
  sectorUnreliableMetrics: string[];
  price: { value: number; asOf: string; currency: string };
  annualVolatilityPct: number | null;
  metrics: Record<string, Metric>;
  financials: { periodEnd: string; revenue: Metric; operatingIncome: Metric;
                netIncome: Metric; freeCashFlow: Metric }[];
  caveats: Caveat[];
};

type Caveat = {
  kind: "fallback_tag" | "stale_input" | "suppressed_composite"
      | "growth_base" | "share_count" | "per_share_split" | "reorganization";
  severity: "info" | "warning" | "critical";
  message: string;
  affectedMetrics: string[];
};

type Score = {
  total: number | null;
  band: "EXCEPTIONAL"|"STRONG"|"WORTH MONITORING"|"SPECULATIVE / INCOMPLETE"|"REJECT"|"INCOMPLETE";
  isComplete: boolean;                   // false until judgment pillars recorded
  dataPointsEarned: number;
  dataPointsAvailable: number;           // < 50 when the sector makes pillars unscorable
  componentsScored: number;              // of 16
  componentsTotal: number;
  pillars: Pillar[];
  judgmentPillars: { name: string; points: number | null; max: number;
                     justification: string | null }[];
  unscorablePillars: { name: string; reason: string }[];
};

// Added 2026-10-24. The five judgment pillars may be written by a MODEL
// (claude -p headless) rather than a person - see INVEST/docs/MODEL_IN_THE_LOOP.md.
// The UI must say which, for the same reason it shows every other provenance.
type JudgmentPillar = {
  name: string;
  points: number | null;
  max: number;
  justification: string | null;
  source: "model" | "analyst";
  modelRun?: {
    at: string;              // ISO timestamp
    validationsPassed: string[];   // which of the 7 checks ran clean
    retries: number;
  };
};

type Thesis = {
  ticker: string; date: string;
  action: "BUY" | "WATCH" | "AVOID";
  score: Score;
  scenarios: {
    bear: Scenario; base: Scenario; bull: Scenario;
    probabilityWeightedReturnPct: number;
    probPositive: number; probHits20Pct: number; probLoss: number;
    rangeCheck: {                        // from valuation.check_scenario_width
      tooNarrow: boolean; annualVolatilityPct: number;
      bearInSigmas: number; bullInSigmas: number;
      warning: string | null;
    };
  };
  reverseDcf: { impliedGrowthPct: number | null; deliveredGrowthPct: number | null;
                interpretation: string };
  catalysts: { description: string; date: string | null; isDated: boolean }[];
  whyThisCouldFail: string[];            // Phase 5 — must be rendered, never collapsed by default
  sources: { label: string; url: string; tier: 1|2|3|4|5|6|7 }[];
};

type Prediction = {
  date: string; ticker: string;
  entryPrice: number; targetPrice: number; horizonMonths: number;
  expectedReturnPct: number;
  probPositive: number | null; probHits20Pct: number | null; probLoss: number | null;
  convictionScore: number | null;
  thesisStatus: "open"|"on_track"|"at_risk"|"thesis_broken"|"target_hit"|"closed_win"|"closed_loss"|"expired";
  notes: string;
  latestReview: {
    reviewDate: string; priceAtReview: number;
    pctMoveSinceEntry: number; pctOfHorizonElapsed: number;
    benchmarkMovePct: number; relativePts: number;
    assumptionsHeld: string | null; assumptionsBroken: string | null;
  } | null;
};
```

---

## 6. Pages

### `/` Dashboard
Open positions vs benchmark, the latest digest's headline, upcoming dated catalysts
(Exelixis' 3 Dec FDA date), macro summary strip, outstanding warnings (no diversified core;
stop-loss contradiction).

**Must show, prominently:** performance as mean, **mean excluding the largest contributor**,
and median. One takeover once made the book look 3 points ahead when it was 1.6 behind.
Showing only the mean would reproduce that distortion.

### `/screen` Screener
TanStack Table over screen results. Columns: ticker, company, score %, **coverage (n/16)**,
price, revenue CAGR, operating margin, ROIC, P/E, FCF yield. Filters mirroring the Python
CLI's flags.

**Two non-negotiables:** (1) render "thinly measured" companies in a **separate section**, never
interleaved — a 93.5% on 6 of 16 components is not comparable to an 81.5% on 15, and sorting
them together once put the least-measured company top; (2) every excluded company is
inspectable with its exclusion reason.

### `/stock/[ticker]` Company detail — the core page

**Judgment provenance.** Five of the nine score pillars may be written by a model rather than a
person. Render each with a small `model` / `analyst` marker, the full written justification
expanded (not behind a disclosure), and — for model-written ones — the validation record. A
reader should be able to see the reasoning that produced a 6/10 moat score and decide whether
they believe it.
Header: name, ticker, price, sector, and **any critical caveat as a banner** (reorganisation,
stale share count, growth base warning).

Then: score gauge with pillar breakdown (showing available vs possible points), financials
table with per-cell provenance tooltips, revenue/margin charts, valuation metrics,
reverse DCF framed as *"the price assumes X%; the company has delivered Y%"*, scenario bars
with the range-width warning, judgment pillars with their written justifications, and a
**"Why this could fail"** section that is expanded by default.

### `/predictions` Track record — **the differentiator, build this well**
Every prediction with its outcome. Benchmark comparison per position over *its own* window.
Calibration: stated probability vs observed frequency. Resolved predictions showing **what
held and what broke**, in the analyst's own words.

**Show the misses at least as prominently as the hits.** The record contains "I said the upside
was capped; it rose 51% on a takeover" — that entry is more valuable to a beginner than any
winner, and the design must not bury it.

**Display `pctOfHorizonElapsed` beside every number.** A 12-month call at 12% elapsed is noise;
the UI must say so rather than letting a green number imply success.

### `/digests`, `/digests/[date]`
Rendered markdown archive. Jargon terms link to the glossary.

### `/macro`
FRED series with trajectory across checkpoints, and a plain-English reading of what the
backdrop implies.

### `/preferences`
Edit the risk profile. **Until it is complete the app must block BUY/WATCH/AVOID display** —
the Python system already enforces this gate and the UI must honour it, not route around it.

---

## 7. Design direction

**Identity: an instrument panel, not a brokerage app.** Brokerage apps are designed to make
trading feel good. This should make *uncertainty legible*.

- **Light default**, dark via toggle, both through MUI `colorSchemes` CSS variables
- **Inter** for UI, **IBM Plex Mono** for every number — tabular figures so columns align
- **Colour carries meaning, not decoration:** green/red only for realised outcomes vs
  benchmark. Scores use a neutral ramp — a 79 is not "good", it is 79.
- **Absent data is visually distinct, never blank:** a dotted-underline "Not available" chip
  with the reason on hover. Blank cells read as zero; that is the one misreading to design out.
- **Coverage is always adjacent to a score.** Never show "93.5%" without "6/16 components".
- Charts: Recharts, no gradients, no 3D, axes always labelled with units, and a visible gap
  where data is missing rather than an interpolated line.

**Motion:** transform/opacity only, as in the course project. No auto-playing carousels.

---

## 8. Build order

| Phase | Deliverable |
|---|---|
| 1 | Scaffold, theme, layout, `fetchInvestApi`, generated types, mock fixtures |
| 2 | `MetricTile` + `UnavailableBadge` + `ProvenanceTooltip` + `formatMetric` — **the honesty primitives come before any page**, because every page depends on them |
| 3 | `/stock/[ticker]` against mocks — the hardest page; build it first to prove the contracts |
| 4 | `/screen` with TanStack Table and the thinly-measured split |
| 5 | `/predictions` with benchmark + calibration |
| 6 | `/`, `/macro`, `/digests`, `/preferences` |
| 7 | Auth, then swap mocks for the live FastAPI service |

Building the honesty primitives first is deliberate: they are the product, and retrofitting
them into finished pages is how they end up as an afterthought.

---

## 9. Acceptance criteria

The app is correct when:

1. No metric with `value: null` renders as `0`, `-`, or an empty cell — anywhere.
2. A score never appears without its coverage count beside it.
3. Thinly-measured companies are never sorted into the same ranked list as well-measured ones.
4. "Why this could fail" is visible without interaction on every thesis page.
5. Performance is shown as mean, ex-largest-contributor and median together.
6. Every prediction displays its elapsed-horizon percentage.
7. Every page with a score, target or scenario carries the not-financial-advice disclaimer.
8. BUY/WATCH/AVOID is suppressed while the preferences file is incomplete.
9. Every figure traceable to a filing exposes its tag, form and accession number.
10. The word "guaranteed" appears nowhere in the UI.
11. **Any judgment written by a model is labelled as such**, with its justification readable
    and its validation record available. A model-authored moat score must not be
    indistinguishable from a human one — that is the same provenance principle the rest of the
    UI enforces on financial data.
