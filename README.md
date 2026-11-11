# Ad Measurement Study

**Public datasets, personal project.** Measuring what marketing actually
causes — with randomized experiments, honest uncertainty, and a monitor for
an e-commerce business.

## The question and the answer

> When a company shows people an ad or sends them an offer, how many extra
> conversions does that cause — and how sure are we?

**Across six public randomized experiments (15.9M users), marketing caused
32% more conversions — pooled risk ratio 1.32, 95% CI 1.18–1.48 — but the
honest headline is the spread: individual studies range from +6% to +87%
(I² = 99.7%), so a channel's own number only comes from its own experiment.**

![Forest plot](figures/forest_plot.png)

📊 **[The deck](deck/ad_measurement_deck.pptx)** (13 slides, written for a
non-technical reader) · 📒 **[The measurement workbook](excel/measurement_tracker.xlsx)**
· 📋 **[The A/B-test playbook](docs/playbook.md)** · 📐 **[Methods](docs/methods.md)**

## Findings

| # | Finding | Where |
|---|---|---|
| 1 | Every one of the six experiments shows a real lift; intervals exclude zero everywhere, and analytic and bootstrap intervals agree in all seven analyses | `results/lift_results.csv` |
| 2 | Criteo display ads: +0.12 pp on a 0.19% base (a 61% relative lift), CI 0.11–0.12 pp, from 13.98M users analysed by assignment | `results/lift_results.csv` |
| 3 | Pooled random-effects RR 1.32 (1.18–1.48); I² 99.7%; leave-one-out moves the pool between 1.26 and 1.40 — reported as a summary of these studies, not a law | `results/meta_results.csv` |
| 4 | Responders are a minority: targeting the top 20% of Criteo users by predicted uplift keeps **68%** of incremental conversions (held-out data); on Hillstrom the model is barely better than random (25% vs 20%) and is reported as weak | `results/uplift_summary.csv` |
| 5 | CUPED on Hillstrom narrowed the interval by only 0.02% — past-year spend barely predicts campaign-window spend; a variance-reduction method is only as good as its covariate | `results/cuped_hillstrom.csv` |
| 6 | The Olist weekly monitor flags 25 weeks: the 2016–17 launch ramp and one Black Friday; late-delivery share and review score never leave their bands | `results/monitor_flags.csv` |
| 7 | Orders >3 days late average **1.86 stars vs 4.29 on time**; adjusted for category, price, freight and seller state the association barely shrinks (−0.073 points/day). Association, not cause — Olist ran no experiment | `results/delay_adjusted_effect.csv` |

## What this repository proves

- **Metric definitions computed two ways.** Campaign KPIs (CTR, CPM, CPC,
  CPA, ROAS-under-assumption) in DuckDB SQL with window functions, totals
  matched exactly against pandas (`results/kpi_crosscheck.csv`) and rebuilt
  as live formulas in the Excel tracker, whose Checks sheet compares them to
  the Python pipeline.
- **Experiments read properly.** Intention to treat, sample-ratio checks,
  covariate balance, MDE for every study, pre-registered inclusion rules
  (committed before any analysis — see the git history of `analysis_plan.md`).
- **Weak results reported weak.** The Hillstrom uplift model and the CUPED
  adjustment both underperform, and both say so in every deliverable.

## Repository layout

```
analysis_plan.md       pre-registered questions, outcomes, inclusion rules
sql/                   kpis.sql, ecommerce.sql (DuckDB views, commented)
src/                   stats.py, meta.py, experiments.py, lift.py, uplift.py,
                       ecommerce.py, kpis.py, audit.py, make_excel.py,
                       make_deck.py, download.py, viz.py
tests/                 known-answer tests (every expected value hand-computed)
results/               every table the pipeline produces (committed)
figures/               forest plot, Qini curves, monitor, delay chart
excel/                 measurement_tracker.xlsx
deck/                  ad_measurement_deck.pptx
dashboards/            CSV feeds + build guide for Tableau Public / Looker Studio
docs/                  playbook.md, methods.md
data/raw/              downloads land here — never committed
```

## Reproduce everything

```bash
git clone <this repo> && cd ad-measurement-study
make venv      # python3 -m venv + pip install -r requirements.txt
make data      # ~800MB of public downloads (Criteo is 300MB)
make report    # rebuilds every table, figure, the workbook and the deck
make test      # 34 known-answer tests
```

Seeds are fixed; a fresh clone reproduces the numbers above. Built and run
on an 8GB MacBook — the 14M-row Criteo file is only ever touched through
DuckDB aggregates and a stratified 2M-row sample.

## Limits — read before quoting

- Public data, personal project: no client, no employer, no business impact.
- The pooled 32% describes these six studies; it transfers to no platform.
- Part B is observational: late delivery is *associated* with worse reviews.
- Olist is a Brazilian marketplace (2016–18); it says nothing about any
  other shop. ROAS figures exist only under a stated $50/conversion
  assumption.
- Tools: Python, DuckDB SQL, Excel, Tableau Public, Looker Studio. No SPSS,
  SAS or Power BI.

## Data credits and licences

| Dataset | Source | Licence / terms |
|---|---|---|
| Criteo Uplift v2.1 | [Criteo AI Lab via Hugging Face](https://huggingface.co/datasets/criteo/criteo-uplift) | CC BY-NC-SA 4.0 |
| Hillstrom e-mail | [MineThatData challenge](https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html) | free for analysis, credited |
| Marketing A/B | [Kaggle: faviovaz/marketing-ab-testing](https://www.kaggle.com/datasets/faviovaz/marketing-ab-testing) | Kaggle terms, credited |
| Facebook ad campaigns | [Kaggle: loveall/clicks-conversion-tracking](https://www.kaggle.com/datasets/loveall/clicks-conversion-tracking) | Kaggle terms, credited |
| Olist e-commerce | [Kaggle: olistbr/brazilian-ecommerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) | CC BY-NC-SA 4.0 (non-commercial) |
| Lenta / X5 / MegaFon | [scikit-uplift mirrors](https://www.uplift-modeling.com/en/latest/api/datasets/index.html) | public uplift datasets, credited |

Raw files are never committed or redistributed by this repository.
