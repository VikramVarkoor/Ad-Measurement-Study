"""Stretch goal: forecast Olist weekly orders with honest backtests.

Three forecasters, scored one-step-ahead with a rolling origin over the
last 16 weeks (refit at every origin, no peeking):

  naive          last week's orders
  mean4          average of the last four weeks
  lightgbm       lags, rolling means and calendar features; quantile
                 models at 10% and 90% give a prediction interval

The input is results/weekly_ecom.csv (committed), so this runs without
any raw-data download. The launch ramp is excluded from scoring: the
business the forecast serves is the steady-state one.

Outputs: results/forecast_backtest.csv, results/forecast_weekly.csv,
figures/forecast_orders.png.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import paths, viz

SEED = 42
TEST_WEEKS = 16
MIN_TRAIN = 20


def load_weekly() -> pd.Series:
    df = pd.read_csv(paths.RESULTS / "weekly_ecom.csv",
                     parse_dates=["purchase_week"])
    s = df.set_index("purchase_week")["orders"].astype(float)
    # drop the final week: it is almost always partial in the export
    return s.iloc[:-1]


def make_features(s: pd.Series) -> pd.DataFrame:
    """Lagged and calendar features; every column uses only past values."""
    f = pd.DataFrame(index=s.index)
    for lag in (1, 2, 3, 4):
        f[f"lag{lag}"] = s.shift(lag)
    f["roll4"] = s.shift(1).rolling(4).mean()
    f["roll8"] = s.shift(1).rolling(8).mean()
    f["trend"] = np.arange(len(s))
    woy = s.index.isocalendar().week.astype(float).to_numpy()
    f["woy_sin"] = np.sin(2 * np.pi * woy / 52.0)
    f["woy_cos"] = np.cos(2 * np.pi * woy / 52.0)
    return f


def naive_forecast(train: pd.Series) -> float:
    return float(train.iloc[-1])


def mean4_forecast(train: pd.Series) -> float:
    return float(train.iloc[-4:].mean())


def _lgbm(alpha: float | None):
    from lightgbm import LGBMRegressor
    kw = dict(n_estimators=250, learning_rate=0.05, num_leaves=7,
              min_child_samples=5, random_state=SEED, n_jobs=1, verbose=-1)
    if alpha is None:
        return LGBMRegressor(objective="regression", **kw)
    return LGBMRegressor(objective="quantile", alpha=alpha, **kw)


def lgbm_forecast(train: pd.Series, feats: pd.DataFrame,
                  target_idx) -> tuple[float, float, float]:
    """Fit on all weeks before target_idx; predict the target week."""
    X = feats.loc[train.index].dropna()
    y = train.loc[X.index]
    x_new = feats.loc[[target_idx]]
    mid = _lgbm(None).fit(X, y).predict(x_new)[0]
    lo = _lgbm(0.10).fit(X, y).predict(x_new)[0]
    hi = _lgbm(0.90).fit(X, y).predict(x_new)[0]
    lo, hi = min(lo, hi), max(lo, hi)
    return float(mid), float(lo), float(hi)


def rolling_backtest(s: pd.Series, test_weeks: int = TEST_WEEKS
                     ) -> pd.DataFrame:
    feats = make_features(s)
    rows = []
    for i in range(len(s) - test_weeks, len(s)):
        train = s.iloc[:i]
        if len(train) < MIN_TRAIN:
            raise ValueError("not enough history to backtest")
        idx = s.index[i]
        mid, lo, hi = lgbm_forecast(train, feats, idx)
        rows.append({
            "purchase_week": idx, "actual": float(s.iloc[i]),
            "naive": naive_forecast(train),
            "mean4": mean4_forecast(train),
            "lightgbm": mid, "lightgbm_lo": lo, "lightgbm_hi": hi,
        })
    return pd.DataFrame(rows)


def score(bt: pd.DataFrame) -> pd.DataFrame:
    out = []
    for model in ("naive", "mean4", "lightgbm"):
        err = bt[model] - bt.actual
        row = {"model": model,
               "mae": float(err.abs().mean()),
               "mape_pct": float((err.abs() / bt.actual).mean() * 100)}
        if model == "lightgbm":
            inside = ((bt.actual >= bt.lightgbm_lo)
                      & (bt.actual <= bt.lightgbm_hi))
            row["interval_coverage_pct"] = float(inside.mean() * 100)
        out.append(row)
    return pd.DataFrame(out)


def plot(s: pd.Series, bt: pd.DataFrame) -> None:
    viz.style()
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9.2, 4.4))
    recent = s.iloc[-40:]
    ax.plot(recent.index, recent.values, color=viz.GRAY, lw=1.6,
            label="Actual orders")
    ax.fill_between(bt.purchase_week, bt.lightgbm_lo, bt.lightgbm_hi,
                    color=viz.BLUE, alpha=0.18,
                    label="LightGBM 10-90% interval")
    ax.plot(bt.purchase_week, bt.lightgbm, color=viz.BLUE, lw=2,
            label="LightGBM (one step ahead)")
    ax.plot(bt.purchase_week, bt.naive, color=viz.ORANGE, lw=1.4,
            ls="--", label="Naive (last week)")
    ax.set_ylabel("Orders per week")
    ax.set_title("Olist weekly orders: rolling-origin backtest, "
                 f"last {len(bt)} weeks")
    ax.legend(frameon=False, loc="lower left", fontsize=9)
    viz.save(fig, paths.FIGURES / "forecast_orders.png")


def run() -> None:
    s = load_weekly()
    bt = rolling_backtest(s)
    sc = score(bt)
    bt_out = bt.copy()
    bt_out["purchase_week"] = bt_out.purchase_week.dt.date
    bt_out.to_csv(paths.RESULTS / "forecast_weekly.csv", index=False,
                  float_format="%.8g")
    sc.to_csv(paths.RESULTS / "forecast_backtest.csv", index=False,
              float_format="%.8g")
    plot(s, bt)
    print(sc.to_string(index=False))


if __name__ == "__main__":
    run()
