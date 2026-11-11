"""Meta-analysis of binary-outcome experiments on the log risk ratio scale.

Fixed-effect (inverse variance) and DerSimonian–Laird random-effects pooling,
heterogeneity (Q, I^2), and a leave-one-out sensitivity table.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps

Z_975 = 1.959963984540054


def log_risk_ratio(x_t: int, n_t: int, x_c: int, n_c: int) -> tuple[float, float]:
    """Log risk ratio and its variance from a 2x2 table.

    A 0.5 continuity correction is applied to every cell when any event count
    is zero (the standard Haldane–Anscombe correction).
    """
    if x_t == 0 or x_c == 0:
        x_t, x_c = x_t + 0.5, x_c + 0.5
        n_t, n_c = n_t + 1, n_c + 1
    log_rr = np.log((x_t / n_t) / (x_c / n_c))
    var = 1 / x_t - 1 / n_t + 1 / x_c - 1 / n_c  # delta-method variance
    return float(log_rr), float(var)


def fixed_effect(effects: np.ndarray, variances: np.ndarray) -> dict:
    """Inverse-variance pooled estimate assuming one common true effect."""
    w = 1 / np.asarray(variances, dtype=float)
    est = float(np.sum(w * effects) / np.sum(w))
    se = float(np.sqrt(1 / np.sum(w)))
    return {"estimate": est, "se": se,
            "ci_low": est - Z_975 * se, "ci_high": est + Z_975 * se}


def heterogeneity(effects: np.ndarray, variances: np.ndarray) -> dict:
    """Cochran's Q and I^2: do the studies disagree more than chance explains?"""
    w = 1 / np.asarray(variances, dtype=float)
    pooled = np.sum(w * effects) / np.sum(w)
    q = float(np.sum(w * (effects - pooled) ** 2))
    k = len(effects)
    df = k - 1
    p = float(sps.chi2.sf(q, df)) if df > 0 else np.nan
    i2 = float(max(0.0, (q - df) / q)) if q > 0 else 0.0
    return {"Q": q, "df": df, "p_value": p, "I2": i2}


def dersimonian_laird(effects: np.ndarray, variances: np.ndarray) -> dict:
    """Random-effects pooling: true effects may differ between studies.

    tau^2 is the DerSimonian–Laird moment estimate, truncated at zero.
    """
    effects = np.asarray(effects, dtype=float)
    variances = np.asarray(variances, dtype=float)
    w = 1 / variances
    het = heterogeneity(effects, variances)
    df = len(effects) - 1
    c = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    tau2 = max(0.0, (het["Q"] - df) / c) if c > 0 else 0.0
    w_star = 1 / (variances + tau2)
    est = float(np.sum(w_star * effects) / np.sum(w_star))
    se = float(np.sqrt(1 / np.sum(w_star)))
    return {"estimate": est, "se": se, "tau2": float(tau2),
            "ci_low": est - Z_975 * se, "ci_high": est + Z_975 * se, **het}


def leave_one_out(studies: pd.DataFrame) -> pd.DataFrame:
    """Re-pool dropping each study in turn. `studies` needs columns
    ['study', 'log_rr', 'var']. Returns one row per dropped study."""
    rows = []
    for dropped in studies["study"]:
        rest = studies[studies["study"] != dropped]
        fe = fixed_effect(rest["log_rr"].values, rest["var"].values)
        re = dersimonian_laird(rest["log_rr"].values, rest["var"].values)
        rows.append({
            "dropped": dropped,
            "fixed_rr": np.exp(fe["estimate"]),
            "random_rr": np.exp(re["estimate"]),
            "random_ci_low": np.exp(re["ci_low"]),
            "random_ci_high": np.exp(re["ci_high"]),
        })
    return pd.DataFrame(rows)
