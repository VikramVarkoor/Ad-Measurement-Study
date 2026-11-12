"""Phase 3: incrementality: lift, intervals and MDE for every experiment.

Everything is computed from DuckDB aggregates (intention to treat, by
assignment), so the 14M-row Criteo file never enters Python memory. The
bootstrap runs on counts via the binomial identity in src/stats.py.

Outputs in results/:
  lift_results.csv       one row per study (+ Criteo's secondary visit outcome)
  cuped_hillstrom.csv    spend lift before/after CUPED, interval narrowing
  segments_hillstrom.csv segment lifts with BH correction, m stated
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import paths
from .experiments import STUDIES, connect, effective_path, group_counts
from . import stats as st

SEED = 42


def verdict(row: dict, mde: float) -> str:
    """Plain words for what the study showed, following the analysis plan."""
    significant = row["ci_low"] > 0 or row["ci_high"] < 0
    if significant:
        return "lift detected" if row["abs_lift"] > 0 else "negative effect detected"
    # null result: could the study even have seen a modest effect?
    modest = 0.10 * row["rate_control"]  # 10% relative lift, per the plan
    return "we could not tell (underpowered for a 10% lift)" if mde > modest \
        else "no meaningful effect (test was powered to see one)"


def run() -> None:
    con = connect()
    rows = []

    jobs = [(key, s, s.outcome_expr, "primary") for key, s in STUDIES.items()]
    # Criteo's secondary outcome: visit (pre-registered as secondary, not in meta)
    jobs.append(("criteo_visit", STUDIES["criteo"], "visit", "secondary"))

    for key, study, outcome, kind in jobs:
        if kind == "secondary":
            row_counts = con.execute(f"""
                SELECT
                    SUM(CASE WHEN {study.treated_expr} THEN 1 ELSE 0 END),
                    SUM(CASE WHEN {study.treated_expr} THEN ({outcome}) ELSE 0 END),
                    SUM(CASE WHEN NOT ({study.treated_expr}) THEN 1 ELSE 0 END),
                    SUM(CASE WHEN NOT ({study.treated_expr}) THEN ({outcome}) ELSE 0 END)
                FROM '{effective_path(study)}'
            """).fetchone()
            n_t, x_t, n_c, x_c = (int(v) for v in row_counts)
        else:
            c = group_counts(study, con)
            n_t, x_t, n_c, x_c = c["n_t"], c["x_t"], c["n_c"], c["x_c"]

        r = st.two_proportion_lift(x_t, n_t, x_c, n_c)
        boot_low, boot_high = st.bootstrap_lift_ci(x_t, n_t, x_c, n_c, seed=SEED)
        mde = st.minimum_detectable_effect(n_t, n_c, r["rate_control"])

        # the two intervals must agree; a mismatch is a bug to chase, not hide
        agree = (abs(boot_low - r["ci_low"]) < 0.25 * (r["ci_high"] - r["ci_low"]) and
                 abs(boot_high - r["ci_high"]) < 0.25 * (r["ci_high"] - r["ci_low"]))

        rows.append({
            "study": key,
            "label": study.label if kind == "primary" else "Criteo (secondary outcome: visit)",
            "channel": study.channel,
            "outcome": outcome if kind == "secondary" else study.outcome_expr,
            "kind": kind,
            "in_meta": study.in_meta and kind == "primary",
            "n_treated": n_t, "n_control": n_c,
            "events_treated": x_t, "events_control": x_c,
            "rate_treated": r["rate_treated"], "rate_control": r["rate_control"],
            "abs_lift_pp": r["abs_lift"] * 100,
            "rel_lift_pct": r["rel_lift"] * 100,
            "ci_low_pp": r["ci_low"] * 100, "ci_high_pp": r["ci_high"] * 100,
            "boot_low_pp": boot_low * 100, "boot_high_pp": boot_high * 100,
            "intervals_agree": agree,
            "z": r["z"], "p_value": r["p_value"],
            "mde_abs_pp": mde * 100,
            "mde_rel_pct": mde / r["rate_control"] * 100,
            "incremental_conversions": r["incremental_conversions"],
            "verdict": verdict(r, mde),
        })

    results = pd.DataFrame(rows)
    results.to_csv(paths.RESULTS / "lift_results.csv", index=False, float_format="%.8g")

    # ---------------------------------------------------------- CUPED (Hillstrom)
    # Outcome: spend (continuous). Covariate: history = past-year spend,
    # measured before the mailing, so it qualifies for CUPED.
    hs = con.execute(f"""
        SELECT history, spend,
               CASE WHEN segment <> 'No E-Mail' THEN 1 ELSE 0 END AS treated
        FROM '{STUDIES["hillstrom"].path}'
    """).df()
    y, x, t = hs["spend"].values, hs["history"].values, hs["treated"].values == 1

    raw = st.continuous_lift(y[t], y[~t])
    adj_y, theta = st.cuped_adjust(y, x)
    adj = st.continuous_lift(adj_y[t], adj_y[~t])
    width_raw = raw["ci_high"] - raw["ci_low"]
    width_adj = adj["ci_high"] - adj["ci_low"]
    cuped = pd.DataFrame([
        {"estimator": "difference in means", **raw, "ci_width": width_raw},
        {"estimator": f"CUPED (theta={theta:.4f}, covariate=history)",
         **adj, "ci_width": width_adj},
    ])
    cuped["interval_narrowing_pct"] = [0.0, (1 - width_adj / width_raw) * 100]
    cuped.to_csv(paths.RESULTS / "cuped_hillstrom.csv", index=False, float_format="%.8g")

    # --------------------------------------------- segments (Hillstrom, with BH)
    # Pre-treatment segments only. m is stated; BH at q = 0.10 per the plan.
    seg_defs = [("channel", "channel"), ("zip_code", "zip_code"), ("newbie", "newbie")]
    seg_rows = []
    for dim, col in seg_defs:
        segs = con.execute(f"""
            SELECT "{col}" AS segment,
                SUM(CASE WHEN segment <> 'No E-Mail' THEN 1 ELSE 0 END)          AS n_t,
                SUM(CASE WHEN segment <> 'No E-Mail' THEN conversion ELSE 0 END) AS x_t,
                SUM(CASE WHEN segment  = 'No E-Mail' THEN 1 ELSE 0 END)          AS n_c,
                SUM(CASE WHEN segment  = 'No E-Mail' THEN conversion ELSE 0 END) AS x_c
            FROM '{STUDIES["hillstrom"].path}'
            GROUP BY "{col}"
        """).df()
        for _, s in segs.iterrows():
            r = st.two_proportion_lift(int(s.x_t), int(s.n_t), int(s.x_c), int(s.n_c))
            seg_rows.append({
                "dimension": dim, "segment": str(s.segment),
                "n": int(s.n_t + s.n_c),
                "abs_lift_pp": r["abs_lift"] * 100,
                "ci_low_pp": r["ci_low"] * 100, "ci_high_pp": r["ci_high"] * 100,
                "p_value": r["p_value"],
            })
    seg = pd.DataFrame(seg_rows)
    seg["m_segments_examined"] = len(seg)
    seg["bh_significant_q10"] = st.benjamini_hochberg(seg["p_value"].values, q=0.10)
    seg.to_csv(paths.RESULTS / "segments_hillstrom.csv", index=False, float_format="%.8g")

    with pd.option_context("display.width", 250):
        print(results[["study", "n_treated", "n_control", "rate_treated", "rate_control",
                       "abs_lift_pp", "ci_low_pp", "ci_high_pp", "boot_low_pp",
                       "boot_high_pp", "intervals_agree", "mde_abs_pp", "verdict"]]
              .round(4).to_string(index=False, float_format="%.8g"))
        print()
        print(cuped.round(4).to_string(index=False, float_format="%.8g"))
        print()
        print(seg.round(4).to_string(index=False, float_format="%.8g"))


if __name__ == "__main__":
    run()
