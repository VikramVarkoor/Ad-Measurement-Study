"""Phase 5: meta-analysis — pool the experiments, say how far to trust it.

Effect size: log risk ratio (base rates span 0.2%–60%, so differences are not
comparable but ratios are). Fixed-effect and DerSimonian–Laird random-effects,
heterogeneity (Q, I²), forest plot, and a leave-one-out table.

Outputs: results/meta_results.csv, results/meta_studies.csv,
results/meta_leave_one_out.csv, figures/forest_plot.png.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import meta, paths, viz
from .experiments import STUDIES, connect, group_counts


def run() -> None:
    con = connect()

    rows = []
    for key, study in STUDIES.items():
        if not study.in_meta:
            continue
        c = group_counts(study, con)
        log_rr, var = meta.log_risk_ratio(c["x_t"], c["n_t"], c["x_c"], c["n_c"])
        rows.append({
            "study": key, "label": study.label, "channel": study.channel,
            "n": c["n_t"] + c["n_c"],
            "x_t": c["x_t"], "n_t": c["n_t"], "x_c": c["x_c"], "n_c": c["n_c"],
            "rr": np.exp(log_rr), "log_rr": log_rr, "var": var,
            "ci_low_rr": np.exp(log_rr - meta.Z_975 * np.sqrt(var)),
            "ci_high_rr": np.exp(log_rr + meta.Z_975 * np.sqrt(var)),
        })
    studies = pd.DataFrame(rows)
    studies.to_csv(paths.RESULTS / "meta_studies.csv", index=False, float_format="%.8g")

    eff, var = studies["log_rr"].values, studies["var"].values
    fe = meta.fixed_effect(eff, var)
    re = meta.dersimonian_laird(eff, var)
    loo = meta.leave_one_out(studies[["study", "log_rr", "var"]])
    loo.to_csv(paths.RESULTS / "meta_leave_one_out.csv", index=False, float_format="%.8g")

    summary = pd.DataFrame([
        {"model": "fixed effect", "rr": np.exp(fe["estimate"]),
         "ci_low": np.exp(fe["ci_low"]), "ci_high": np.exp(fe["ci_high"]),
         "tau2": 0.0, "Q": re["Q"], "I2": re["I2"],
         "loo_rr_min": loo["fixed_rr"].min(), "loo_rr_max": loo["fixed_rr"].max()},
        {"model": "random effects (DL)", "rr": np.exp(re["estimate"]),
         "ci_low": np.exp(re["ci_low"]), "ci_high": np.exp(re["ci_high"]),
         "tau2": re["tau2"], "Q": re["Q"], "I2": re["I2"],
         "loo_rr_min": loo["random_rr"].min(), "loo_rr_max": loo["random_rr"].max()},
    ])
    summary.to_csv(paths.RESULTS / "meta_results.csv", index=False, float_format="%.8g")

    # ------------------------------------------------------------ forest plot
    viz.style()
    import matplotlib.pyplot as plt

    s = studies.sort_values("n", ascending=True).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ypos = np.arange(len(s))

    ax.axvline(1.0, color=viz.GRID, lw=1)
    # one point + whisker per study; marker area tracks inverse-variance weight
    w = 1 / s["var"]
    sizes = 40 + 160 * (w / w.max())
    for i, row in s.iterrows():
        ax.plot([row.ci_low_rr, row.ci_high_rr], [i, i], color=viz.BLUE, lw=2)
    ax.scatter(s["rr"], ypos, s=sizes, color=viz.BLUE, zorder=3)

    # pooled random-effects diamond under the studies
    d_y = -1.1
    d = np.exp([re["ci_low"], re["estimate"], re["ci_high"]])
    ax.fill([d[0], d[1], d[2], d[1]], [d_y, d_y + 0.42, d_y, d_y - 0.42],
            color=viz.ORANGE, lw=0)

    labels = [f"{row.label}\n(n={row.n:,})" for _, row in s.iterrows()]
    ax.set_yticks(list(ypos) + [d_y])
    ax.set_yticklabels(labels + ["Pooled (random effects)"])
    ax.set_xscale("log")
    ticks = [0.9, 1.0, 1.2, 1.5, 2.0, 3.0]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t:g}" for t in ticks])
    ax.set_xlabel("Risk ratio (treated / control), log scale — 1.0 = no effect")
    ax.set_title("Every treatment lifted conversions, but by very different amounts")
    ax.grid(axis="y", visible=False)
    viz.save(fig, paths.FIGURES / "forest_plot.png")

    print(studies[["study", "n", "rr", "ci_low_rr", "ci_high_rr"]].round(4).to_string(index=False, float_format="%.8g"))
    print()
    print(summary.round(4).to_string(index=False, float_format="%.8g"))
    print()
    print(loo.round(4).to_string(index=False, float_format="%.8g"))


if __name__ == "__main__":
    run()
