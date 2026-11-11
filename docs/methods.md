# Methods in one page

**Lift.** For each randomized study: treated rate − control rate (absolute),
divided by the control rate (relative), by assignment (intention to treat).
95% interval: Wald with unpooled variance. Test: two-proportion z with pooled
variance. Both from aggregate counts, so the 14M-row Criteo file is never
loaded — DuckDB `GROUP BY` does the work.

**Bootstrap.** For a binary outcome, resampling n users with replacement and
summing outcomes is a Binomial(n, p̂) draw, so the 2,000-draw percentile
bootstrap runs on counts alone (seed 42). It must agree with the analytic
interval; in all seven analyses it does (`intervals_agree` in
`results/lift_results.csv`).

**Sample ratio check.** χ² of observed vs intended split, df=1; mismatch
declared at p < 0.001. Where no intended split is documented (Lenta,
MegaFon) the observed share is recorded and the test skipped.

**MDE.** (z₀.₉₇₅ + z₀.₈₀)·SE at the control rate: the smallest absolute lift
the study could reliably detect at 80% power, α=0.05. Nulls are read
against it ("we could not tell" vs "no meaningful effect").

**CUPED.** Y′ = Y − θ(X − X̄) with θ the OLS slope on all units; X must be
pre-treatment. On Hillstrom (X = past-year spend, Y = campaign-window spend)
θ≈0.001 and the interval narrowed 0.02% — reported as a near-null: CUPED
only helps when the covariate predicts the outcome.

**Multiplicity.** Segment scans state m and apply Benjamini–Hochberg at
q=0.10 (`segments_hillstrom.csv`, m=8).

**Uplift model.** Two LightGBM classifiers (treated / control); score =
difference of predicted conversion probabilities. 70/30 split stratified by
treatment; evaluation only on the held-out 30%: Qini curve vs random and the
share of incremental conversions kept when targeting the top 20%.
Criteo: 68% kept. Hillstrom: 25% vs 20% random — weak, and said so.

**Meta-analysis.** Effect = log risk ratio (base rates 0.2%–60% make
differences incomparable); variance by the delta method with Haldane–
Anscombe correction if a cell is zero. Fixed-effect (inverse variance) and
DerSimonian–Laird random-effects; heterogeneity via Cochran's Q and
I² = (Q−df)/Q; leave-one-out re-pooling per study. Result: RE RR 1.32
(1.18–1.48), I² 99.7% — the pooled number is a summary of these six
studies, not a transferable constant.

**Part B (observational).** Weekly monitor: mean ± 3σ of the stable 2018
stretch; flags say when, never why. Diagnosis: review score vs days late,
raw and adjusted (OLS with category, log price, log freight, seller state;
one row per order). Adjustment moves −0.074 to −0.073 points/day — the
association survives, and is still labelled association.

**Reproducibility.** `make data` downloads the public files; `make report`
rebuilds every table, figure, the workbook and the deck; `make test` runs
the known-answer tests (every expected value hand-computed first). Seeds are
fixed (42) end to end.
