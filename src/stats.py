"""Core experiment statistics: lift, intervals, SRM, power, CUPED, multiplicity.

Every function works from aggregate counts where possible, so the full 14M-row
Criteo table never has to be loaded into memory.
"""
from __future__ import annotations

import numpy as np
from scipy import stats as sps

Z_975 = 1.959963984540054  # z for a two-sided 95% interval


def two_proportion_lift(x_t: int, n_t: int, x_c: int, n_c: int) -> dict:
    """Lift of a binary outcome between treated and control, with a 95% interval.

    Interval: Wald with unpooled variance (the standard A/B-test interval).
    Test: two-proportion z-test with pooled variance under the null.
    All inputs are counts, so this runs on aggregates of any size.
    """
    if min(n_t, n_c) <= 0:
        raise ValueError("group sizes must be positive")
    if not (0 <= x_t <= n_t and 0 <= x_c <= n_c):
        raise ValueError("event counts must lie within group sizes")

    p_t, p_c = x_t / n_t, x_c / n_c
    lift = p_t - p_c

    se_unpooled = np.sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c)
    ci_low, ci_high = lift - Z_975 * se_unpooled, lift + Z_975 * se_unpooled

    p_pool = (x_t + x_c) / (n_t + n_c)
    se_pooled = np.sqrt(p_pool * (1 - p_pool) * (1 / n_t + 1 / n_c))
    z = lift / se_pooled if se_pooled > 0 else np.nan
    p_value = 2 * sps.norm.sf(abs(z)) if np.isfinite(z) else np.nan

    return {
        "n_treated": n_t,
        "n_control": n_c,
        "rate_treated": p_t,
        "rate_control": p_c,
        "abs_lift": lift,
        "rel_lift": lift / p_c if p_c > 0 else np.nan,
        "se": se_unpooled,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "z": z,
        "p_value": p_value,
        "incremental_conversions": lift * n_t,
    }


def bootstrap_lift_ci(
    x_t: int, n_t: int, x_c: int, n_c: int,
    n_boot: int = 2000, seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap interval for the absolute lift.

    For a 0/1 outcome, resampling n users with replacement and summing their
    outcomes is exactly a Binomial(n, p-hat) draw, so the bootstrap can run on
    counts alone. That identity is what makes a 14M-row bootstrap instant.
    """
    rng = np.random.default_rng(seed)
    bt = rng.binomial(n_t, x_t / n_t, size=n_boot) / n_t
    bc = rng.binomial(n_c, x_c / n_c, size=n_boot) / n_c
    lifts = bt - bc
    return float(np.quantile(lifts, 0.025)), float(np.quantile(lifts, 0.975))


def srm_check(n_t: int, n_c: int, expected_treated_share: float) -> dict:
    """Sample ratio mismatch: chi-square test of observed vs intended split."""
    total = n_t + n_c
    expected = np.array([total * expected_treated_share, total * (1 - expected_treated_share)])
    observed = np.array([n_t, n_c])
    chi2 = float(((observed - expected) ** 2 / expected).sum())
    p = float(sps.chi2.sf(chi2, df=1))
    return {
        "observed_share": n_t / total,
        "expected_share": expected_treated_share,
        "chi2": chi2,
        "p_value": p,
        "mismatch": p < 0.001,
    }


def minimum_detectable_effect(
    n_t: int, n_c: int, p_c: float,
    alpha: float = 0.05, power: float = 0.80,
) -> float:
    """Smallest absolute lift the test could reliably detect.

    Standard approximation: MDE = (z_{1-a/2} + z_{power}) * SE, with the
    baseline rate used for both groups' variance.
    """
    z_alpha = sps.norm.ppf(1 - alpha / 2)
    z_power = sps.norm.ppf(power)
    se = np.sqrt(p_c * (1 - p_c) * (1 / n_t + 1 / n_c))
    return float((z_alpha + z_power) * se)


def cuped_adjust(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, float]:
    """CUPED: remove from Y the part predictable from a pre-treatment covariate X.

    theta is the OLS slope of Y on X computed on all units (treated + control
    together), which keeps the adjustment unbiased for the lift. Returns the
    adjusted outcome and theta.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    vx = x.var(ddof=1)
    if vx == 0:
        return y.copy(), 0.0
    theta = float(np.cov(x, y, ddof=1)[0, 1] / vx)
    return y - theta * (x - x.mean()), theta


def continuous_lift(y_t: np.ndarray, y_c: np.ndarray) -> dict:
    """Difference in means with a 95% interval (Welch), for spend-like outcomes."""
    y_t = np.asarray(y_t, dtype=float)
    y_c = np.asarray(y_c, dtype=float)
    diff = y_t.mean() - y_c.mean()
    se = np.sqrt(y_t.var(ddof=1) / len(y_t) + y_c.var(ddof=1) / len(y_c))
    return {
        "mean_treated": float(y_t.mean()),
        "mean_control": float(y_c.mean()),
        "abs_lift": float(diff),
        "se": float(se),
        "ci_low": float(diff - Z_975 * se),
        "ci_high": float(diff + Z_975 * se),
    }


def benjamini_hochberg(p_values, q: float = 0.10) -> np.ndarray:
    """BH step-up: returns a boolean array, True where the test is significant.

    Sort the p-values; find the largest rank k with p_(k) <= k/m * q; everything
    at or below that rank is declared significant.
    """
    p = np.asarray(p_values, dtype=float)
    m = len(p)
    order = np.argsort(p)
    thresholds = (np.arange(1, m + 1) / m) * q
    below = p[order] <= thresholds
    significant = np.zeros(m, dtype=bool)
    if below.any():
        k = np.max(np.nonzero(below)[0])
        significant[order[: k + 1]] = True
    return significant


def bonferroni_alpha(alpha: float, n_tests: int) -> float:
    return alpha / n_tests
