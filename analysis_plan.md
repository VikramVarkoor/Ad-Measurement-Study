# Analysis plan — Ad Measurement Study

**Status:** committed before any analysis was run. The git timestamp of this file is the
proof that the questions, metrics and inclusion rules were fixed before results were seen.

**Public data, personal project.** Nothing here measures a real client or employer.

---

## The two questions

**Part A (causal).** When a company shows people an ad or sends them a marketing offer,
how many extra conversions does that cause, how sure are we, and who responds most?
Answered with randomized experiments only, so the lift estimates are causal.

**Part B (observational).** When an online shop's customers are unhappy, what is the data
telling the business to fix first? Answered with the Olist orders data, so results are
associations, never causes, and every deliverable says so.

## Datasets and the fixed outcome for each

| Study | Treatment | Outcome (fixed in advance) | Expected design |
|---|---|---|---|
| Criteo Uplift v2.1 | Display advertising | `conversion` (binary) | ~14M users, ~85% treated |
| Hillstrom | Any e-mail vs no e-mail (both e-mail arms pooled — they share one control, so they are **not** independent studies) | `conversion` (binary); `spend` secondary for CUPED | 64k customers, 2/3 treated |
| Marketing A/B (Kaggle) | Ad vs public service announcement | `converted` (binary) | ~588k users, ~96% ad |
| Lenta | Retail marketing communication | `response_att` (binary) | ~687k clients |
| X5 RetailHero | SMS promotion | `target` (binary) | ~200k clients, 50/50 |
| MegaFon | Telecom offer (synthetic features) | `conversion` (binary) | ~600k clients |
| Facebook ads (KAG) | — observational campaign data, **not** an experiment | KPI layer only, never in the meta-analysis | ~1,143 ads |
| Olist | — observational orders, **not** an experiment | Part B only | ~100k orders |

If a file's real columns differ from the table above, the file wins and the difference is
recorded in the data quality log.

## Meta-analysis inclusion rules (fixed before results)

A study enters the meta-analysis **only if**:
1. assignment to treatment was random,
2. the outcome is a yes/no event,
3. both group sizes are known.

- Any study where assignment is unclear is excluded, with the reason in the README.
- Every included study stays in, including null and negative results.
- The outcome per study is the one fixed in the table above, chosen before analysis.
- Effect size: log risk ratio. Pooling: fixed-effect and DerSimonian–Laird random-effects,
  both reported, with Q, I², and a leave-one-out table.

## What counts as "no effect"

A study's result is reported as **"we could not tell"** (not "no effect") when its 95%
interval crosses zero **and** its minimum detectable effect (80% power, α = 0.05) is larger
than the observed control-rate × 10% relative lift. A result only earns the words
"no meaningful effect" when the interval excludes lifts bigger than that.

## Analysis rules

- **Intention to treat:** every comparison is by assignment, never by exposure.
- **Sample ratio check first:** a chi-square test of observed vs intended split per study;
  a p < 0.001 mismatch is investigated before any lift is reported.
- **Uncertainty two ways:** analytic interval for a difference of proportions and a
  2,000-draw bootstrap (seed 42). Disagreement is a bug to find, not to ignore.
- **Segments:** any segment scan reports how many segments were examined and applies
  Benjamini–Hochberg at q = 0.10.
- **Uplift model:** two-model approach, evaluated only on a held-out split against random
  targeting via a Qini curve. A weak result is reported as weak.
- **Part B:** weekly control-chart monitor (mean ± 3σ of a stable stretch); the
  late-delivery → review-score association is adjusted for product category, price,
  freight and seller state, and still labelled association.

## Part B issue tree

```
Customer unhappiness (low review score)
├── Delivery        → H1: late orders get worse reviews than on-time orders
├── Product         → H2: some categories are rated worse at any delivery speed
├── Price/freight   → H3: high freight relative to price lowers scores
└── Seller          → H4: a minority of seller states account for most late orders
```

Each hypothesis is tested once, with the test named before looking: H1 by delay buckets +
adjusted regression, H2–H4 as descriptive cuts feeding the recommendation table.
