"""Phase 4: two-model uplift: who did the marketing actually move?

Criteo: a 2M-row stratified sample (DuckDB, fixed seed) keeps the treatment
share; features are the 12 anonymized floats. Hillstrom: the full 64k rows
with one-hot categoricals. Both are scored ONLY on a held-out split and
compared to random targeting with a Qini curve.

Outputs: results/uplift_summary.csv, results/uplift_targeting.csv,
results/uplift_deciles_{study}.csv, figures/qini_{study}.png.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split

from . import paths, viz
from .experiments import STUDIES, connect, effective_path

SEED = 42
SAMPLE_PER_ARM = {"treated": 1_700_000, "control": 300_000}  # ~2M, keeps the 85/15 share


def two_model_fit_score(X_tr, t_tr, y_tr, X_te) -> np.ndarray:
    """Fit conversion models on treated and control separately; the uplift
    score is the gap between the two predicted conversion probabilities."""
    params = dict(
        n_estimators=300, learning_rate=0.05, num_leaves=31,
        min_child_samples=200, subsample=0.8, colsample_bytree=0.8,
        random_state=SEED, n_jobs=4, verbose=-1,
    )
    m1 = LGBMClassifier(**params).fit(X_tr[t_tr == 1], y_tr[t_tr == 1])
    m0 = LGBMClassifier(**params).fit(X_tr[t_tr == 0], y_tr[t_tr == 0])
    return m1.predict_proba(X_te)[:, 1] - m0.predict_proba(X_te)[:, 1]


def qini_curve(score, t, y, n_points: int = 101):
    """Cumulative incremental conversions as we target more of the ranking.

    At share phi (by descending uplift score):
        qini(phi) = Y_T(phi) - Y_C(phi) * N_T(phi) / N_C(phi)
    i.e. conversions among treated minus what the control users in the same
    slice say would have happened anyway, rescaled to the treated count.
    The random baseline is a straight line to the overall incremental total.
    """
    order = np.argsort(-score)
    t, y = np.asarray(t)[order], np.asarray(y)[order]
    n = len(t)
    cum_nt = np.cumsum(t)
    cum_nc = np.cumsum(1 - t)
    cum_yt = np.cumsum(y * t)
    cum_yc = np.cumsum(y * (1 - t))

    idx = np.unique(np.linspace(0, n - 1, n_points).astype(int))
    phi = (idx + 1) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        qini = cum_yt[idx] - cum_yc[idx] * np.where(cum_nc[idx] > 0,
                                                    cum_nt[idx] / cum_nc[idx], 0.0)
    total = qini[-1]
    random_line = phi * total
    auqc = float(np.trapezoid(qini - random_line, phi))  # area above random
    return phi, qini, random_line, auqc


def decile_table(score, t, y) -> pd.DataFrame:
    """Observed lift inside each decile of the predicted-uplift ranking."""
    df = pd.DataFrame({"score": score, "t": t, "y": y})
    df["decile"] = pd.qcut(df["score"].rank(method="first", ascending=False),
                           10, labels=range(1, 11))
    rows = []
    for d, g in df.groupby("decile", observed=True):
        nt, nc = int((g.t == 1).sum()), int((g.t == 0).sum())
        rt = g.loc[g.t == 1, "y"].mean() if nt else np.nan
        rc = g.loc[g.t == 0, "y"].mean() if nc else np.nan
        rows.append({"decile": int(d), "n": len(g), "n_treated": nt, "n_control": nc,
                     "rate_treated": rt, "rate_control": rc,
                     "observed_lift_pp": (rt - rc) * 100,
                     "mean_predicted_uplift_pp": g.score.mean() * 100})
    return pd.DataFrame(rows)


def targeting_share(score, t, y, top_share: float = 0.20) -> dict:
    """If only the top X% by predicted uplift could be messaged, what share of
    the incremental conversions would be kept?"""
    order = np.argsort(-score)
    k = int(len(score) * top_share)
    top = order[:k]

    def incremental(ix):
        tt, yy = t[ix], y[ix]
        nt, nc = (tt == 1).sum(), (tt == 0).sum()
        if nt == 0 or nc == 0:
            return 0.0
        return (yy[tt == 1].mean() - yy[tt == 0].mean()) * nt

    inc_top = incremental(top)
    inc_all = incremental(np.arange(len(score)))
    return {"top_share": top_share, "incremental_top": inc_top,
            "incremental_total": inc_all,
            "share_kept": inc_top / inc_all if inc_all else np.nan}


def load_criteo():
    con = connect()
    con.execute("SET threads=1")  # keeps REPEATABLE reservoir sampling deterministic
    path = effective_path(STUDIES["criteo"])
    # Stratified fixed-seed sample per arm, keeping the 85/15 treatment share.
    # The filter sits INSIDE a derived table because a `USING SAMPLE` written
    # after a plain WHERE binds to the base-table scan and samples BEFORE the
    # filter, which silently shrank the control arm to ~45k rows when tried.
    df = con.execute(f"""
        SELECT * FROM (
            SELECT f0,f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11, treatment, conversion
            FROM '{path}' WHERE treatment = 1
        ) treated_pool USING SAMPLE reservoir({SAMPLE_PER_ARM['treated']} ROWS) REPEATABLE ({SEED})
        UNION ALL
        SELECT * FROM (
            SELECT f0,f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11, treatment, conversion
            FROM '{path}' WHERE treatment = 0
        ) control_pool USING SAMPLE reservoir({SAMPLE_PER_ARM['control']} ROWS) REPEATABLE ({SEED})
    """).df()
    share = df["treatment"].mean()
    assert 0.80 < share < 0.90, f"sample treatment share {share:.3f} drifted from 85%"
    feats = [f"f{i}" for i in range(12)]
    X = df[feats].astype(np.float32).values
    return X, df["treatment"].values, df["conversion"].values


def load_hillstrom():
    df = pd.read_csv(STUDIES["hillstrom"].path)
    df["treated"] = (df["segment"] != "No E-Mail").astype(int)
    X = pd.get_dummies(
        df[["recency", "history", "mens", "womens", "newbie", "zip_code", "channel"]],
        columns=["zip_code", "channel"], dtype=np.float32,
    ).astype(np.float32).values
    return X, df["treated"].values, df["conversion"].values


def qini_plot(study_label, phi, qini, random_line, auqc, out_path):
    viz.style()
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.plot(phi * 100, qini, color=viz.BLUE, lw=2, label="Uplift model")
    ax.plot(phi * 100, random_line, color=viz.GRAY, lw=2, ls="--", label="Random targeting")
    ax.set_xlabel("Share of users targeted, ranked by predicted uplift (%)")
    ax.set_ylabel("Cumulative incremental conversions")
    ax.set_title(f"{study_label}: model vs random targeting (held-out data)")
    ax.legend(frameon=False, loc="lower right")
    ax.text(0.02, 0.95, f"Area above random = {auqc:,.0f}",
            transform=ax.transAxes, color=viz.TEXT_2, va="top")
    viz.save(fig, out_path)


def run_study(key: str, label: str, loader) -> dict:
    X, t, y = loader()
    X_tr, X_te, t_tr, t_te, y_tr, y_te = train_test_split(
        X, t, y, test_size=0.3, random_state=SEED, stratify=t
    )
    score = two_model_fit_score(X_tr, t_tr, y_tr, X_te)

    phi, qini, random_line, auqc = qini_curve(score, t_te, y_te)
    qini_plot(label, phi, qini, random_line, auqc, paths.FIGURES / f"qini_{key}.png")

    decile_table(score, t_te, y_te).to_csv(
        paths.RESULTS / f"uplift_deciles_{key}.csv", index=False, float_format="%.8g")

    tgt = targeting_share(score, t_te, y_te, 0.20)
    return {
        "study": key, "holdout_n": len(t_te),
        "qini_area_above_random": auqc,
        "incremental_total_holdout": tgt["incremental_total"],
        "incremental_in_top20": tgt["incremental_top"],
        "share_kept_top20": tgt["share_kept"],
    }


def run() -> None:
    summaries = []
    summaries.append(run_study("criteo", "Criteo display ads", load_criteo))
    summaries.append(run_study("hillstrom", "Hillstrom e-mail", load_hillstrom))
    out = pd.DataFrame(summaries)
    out.to_csv(paths.RESULTS / "uplift_summary.csv", index=False, float_format="%.8g")
    pd.DataFrame([
        {"study": s["study"], "top_share": 0.20,
         "share_of_incremental_kept": s["share_kept_top20"]}
        for s in summaries
    ]).to_csv(paths.RESULTS / "uplift_targeting.csv", index=False, float_format="%.8g")
    print(out.round(4).to_string(index=False, float_format="%.8g"))


if __name__ == "__main__":
    run()
