"""Phase 6: Olist weekly monitor and the late-delivery diagnosis.

The monitor: weekly orders with a control-chart band (mean ± 3σ of a stable
stretch) — it says WHEN a metric moved beyond normal noise, never why.

The diagnosis: review score vs delivery delay, raw and then adjusted for
product category, price, freight and seller state. Olist is observational,
so every number here is an association, and the outputs say so.

Outputs in results/: weekly_ecom.csv, monitor_flags.csv, delay_vs_review.csv,
delay_adjusted_effect.csv, late_by_seller_state.csv, recommendation.csv,
join_trap_check.csv. Figures: monitor_orders.png, delay_vs_review.png.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from . import paths, viz
from .experiments import connect

# The stable stretch for the control band: the 2018 plateau. 2016–17 is a
# launch ramp (every week would flag "low" against it), and the final weeks
# are truncated by the data's end, so the band is estimated where the
# business ran at steady state.
STABLE_START, STABLE_END = "2018-01-01", "2018-07-31"
# Display window: full weeks with meaningful volume.
SERIES_START, SERIES_END = "2017-01-01", "2018-08-20"


def load_olist(con) -> None:
    o = paths.OLIST_DIR
    tables = {
        "orders": "olist_orders_dataset.csv",
        "items": "olist_order_items_dataset.csv",
        "payments": "olist_order_payments_dataset.csv",
        "reviews": "olist_order_reviews_dataset.csv",
        "customers": "olist_customers_dataset.csv",
        "sellers": "olist_sellers_dataset.csv",
        "products": "olist_products_dataset.csv",
        "category_translation": "product_category_name_translation.csv",
    }
    for name, f in tables.items():
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM '{o / f}'")
    con.execute((paths.SQL / "ecommerce.sql").read_text())


def run() -> None:
    con = connect()
    load_olist(con)

    # ------------------------------------------------ join trap must hold
    trap = con.execute("SELECT * FROM join_trap_check").df()
    trap.to_csv(paths.RESULTS / "join_trap_check.csv", index=False, float_format="%.8g")
    assert trap["inflation_factor"].iloc[0] > 1.0, \
        "items x payments should inflate revenue; check the join logic"

    weekly = con.execute(f"""
        SELECT * FROM weekly_ecom
        WHERE purchase_week BETWEEN DATE '{SERIES_START}' AND DATE '{SERIES_END}'
        ORDER BY purchase_week
    """).df()
    weekly.to_csv(paths.RESULTS / "weekly_ecom.csv", index=False, float_format="%.8g")
    con.execute("SELECT * FROM week_over_week").df().to_csv(
        paths.RESULTS / "week_over_week.csv", index=False, float_format="%.8g")

    # ------------------------------------------------ control-chart flags
    weekly["purchase_week"] = pd.to_datetime(weekly["purchase_week"])
    stable = weekly[(weekly.purchase_week >= pd.Timestamp(STABLE_START))
                    & (weekly.purchase_week <= pd.Timestamp(STABLE_END))]
    flags_all = []
    bands = {}
    for metric in ["orders", "late_share", "avg_review_score"]:
        mu, sd = stable[metric].mean(), stable[metric].std(ddof=1)
        lo, hi = mu - 3 * sd, mu + 3 * sd
        bands[metric] = (mu, sd, lo, hi)
        f = weekly[(weekly[metric] < lo) | (weekly[metric] > hi)][
            ["purchase_week", metric]].copy()
        f["metric"] = metric
        f["direction"] = np.where(f[metric] > hi, "above band", "below band")
        f = f.rename(columns={metric: "value"})
        flags_all.append(f)
    flags = pd.concat(flags_all, ignore_index=True)
    flags["stable_stretch"] = f"{STABLE_START}..{STABLE_END}"
    flags.to_csv(paths.RESULTS / "monitor_flags.csv", index=False, float_format="%.8g")

    # ------------------------------------------------ monitor figure (orders)
    viz.style()
    import matplotlib.pyplot as plt
    mu, sd, lo, hi = bands["orders"]
    fig, ax = plt.subplots(figsize=(8.0, 4.2))
    wk = pd.to_datetime(weekly["purchase_week"])
    ax.axhspan(lo, hi, color=viz.GRID, alpha=0.5, lw=0,
               label="Control band (stable 2018 mean ± 3σ)")
    ax.plot(wk, weekly["orders"], color=viz.BLUE, lw=2, label="Orders per week")
    out = (weekly["orders"] < lo) | (weekly["orders"] > hi)
    ax.scatter(wk[out], weekly.loc[out, "orders"], color=viz.RED, zorder=3, s=28,
               label="Outside the band")
    bf = weekly.loc[weekly["orders"].idxmax()]
    ax.annotate("Black Friday 2017", (pd.Timestamp(bf.purchase_week), bf.orders),
                xytext=(10, -2), textcoords="offset points", color=viz.TEXT_2)
    ax.set_title("Weekly orders: growth ramp, a Black Friday spike, then a 2018 plateau")
    ax.set_ylabel("Delivered orders per purchase week")
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    viz.save(fig, paths.FIGURES / "monitor_orders.png")

    # ------------------------------------------------ delay vs review (raw)
    dvr = con.execute("SELECT * FROM delay_vs_review").df()
    dvr.to_csv(paths.RESULTS / "delay_vs_review.csv", index=False, float_format="%.8g")

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    labels = ["On time", "1–3 days late", ">3 days late"]
    colors = [viz.BLUE, viz.YELLOW, viz.RED]
    bars = ax.bar(labels, dvr["avg_review_score"], color=colors, width=0.62)
    for b, v in zip(bars, dvr["avg_review_score"]):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.05, f"{v:.2f}",
                ha="center", color=viz.TEXT)
    ax.set_ylim(0, 5)
    ax.set_ylabel("Average review score (1–5)")
    ax.set_title("Late orders get much worse reviews — association, not proof of cause")
    viz.save(fig, paths.FIGURES / "delay_vs_review.png")

    # ------------------------------------------------ adjusted association
    # One row per order: a multi-item order would otherwise repeat and get
    # extra weight, so category and seller state are reduced to the order's
    # first (alphabetically lowest item id) inside SQL before the regression.
    df = con.execute("""
        WITH first_item AS (
            SELECT order_id, MIN(order_item_id) AS order_item_id
            FROM items GROUP BY order_id
        ),
        order_cat AS (
            SELECT i.order_id,
                   COALESCE(t.product_category_name_english,
                            p.product_category_name, 'unknown') AS category,
                   s.seller_state
            FROM items i
            JOIN first_item fi USING (order_id, order_item_id)
            JOIN products p USING (product_id)
            LEFT JOIN category_translation t USING (product_category_name)
            JOIN sellers s USING (seller_id)
        )
        SELECT f.review_score, f.days_late, f.revenue, f.freight,
               c.category, c.seller_state
        FROM order_facts f
        JOIN order_cat c USING (order_id)
        WHERE f.review_score IS NOT NULL
    """).df()
    df["days_late_pos"] = df["days_late"].clip(lower=0)
    df["log_price"] = np.log1p(df["revenue"])
    df["log_freight"] = np.log1p(df["freight"])

    raw_model = smf.ols("review_score ~ days_late_pos", data=df).fit()
    adj_model = smf.ols(
        "review_score ~ days_late_pos + log_price + log_freight"
        " + C(category) + C(seller_state)", data=df).fit()

    raw_b = raw_model.params["days_late_pos"]
    adj_b = adj_model.params["days_late_pos"]
    eff = pd.DataFrame([
        {"model": "raw", "points_per_day_late": raw_b,
         "ci_low": raw_model.conf_int().loc["days_late_pos", 0],
         "ci_high": raw_model.conf_int().loc["days_late_pos", 1],
         "n": int(raw_model.nobs)},
        {"model": "adjusted (category, price, freight, seller state)",
         "points_per_day_late": adj_b,
         "ci_low": adj_model.conf_int().loc["days_late_pos", 0],
         "ci_high": adj_model.conf_int().loc["days_late_pos", 1],
         "n": int(adj_model.nobs)},
    ])
    eff["shrink_vs_raw_pct"] = [0.0, (1 - adj_b / raw_b) * 100]
    eff["interpretation"] = "association only — Olist is observational"
    eff.to_csv(paths.RESULTS / "delay_adjusted_effect.csv", index=False, float_format="%.8g")

    # ------------------------------------------------ where the lates sit
    state = con.execute("SELECT * FROM late_by_seller_state").df()
    state.to_csv(paths.RESULTS / "late_by_seller_state.csv", index=False, float_format="%.8g")

    # ------------------------------------------------ the recommendation
    late_share = float((weekly["late_share"] * weekly["orders"]).sum()
                       / weekly["orders"].sum())
    on_time = dvr.loc[dvr.delay_bucket == "1. on time"]
    very_late = dvr.loc[dvr.delay_bucket == "3. >3 days late"]
    gap = float(on_time["avg_review_score"].iloc[0]
                - very_late["avg_review_score"].iloc[0])
    n_very_late = int(very_late["orders"].iloc[0])
    n_reviewed = int(dvr["orders"].sum())
    upside = gap * n_very_late / n_reviewed  # if >3-day lates reviewed like on-time
    rec = pd.DataFrame([{
        "finding": (f">3-day-late orders score {gap:.2f} points below on-time "
                    f"orders ({very_late['avg_review_score'].iloc[0]:.2f} vs "
                    f"{on_time['avg_review_score'].iloc[0]:.2f}); the association "
                    f"survives adjustment at {adj_b:.3f} points per day late"),
        "so_what": (f"{late_share:.1%} of delivered orders arrive late; the worst "
                    "bucket drives most 1–2 star reviews"),
        "action": ("start with the seller states at the top of "
                   "late_by_seller_state.csv: set delivery-promise buffers and "
                   "carrier SLAs there first"),
        "expected_effect": (f"up to ~{upside:.2f} points on the average review "
                            f"score if >3-day lates reviewed like on-time orders "
                            "— an upper bound, association only"),
        "confidence": ("medium: large sample and the association survives "
                       "controls, but no experiment and unmeasured confounders "
                       "(e.g. carrier, distance) remain"),
    }])
    rec.to_csv(paths.RESULTS / "recommendation.csv", index=False, float_format="%.8g")

    print(trap.round(3).to_string(index=False, float_format="%.8g"))
    print()
    print(dvr.round(3).to_string(index=False, float_format="%.8g"))
    print()
    print(eff.round(4).to_string(index=False, float_format="%.8g"))
    print()
    print(state.head(8).round(3).to_string(index=False, float_format="%.8g"))
    print()
    print(f"flagged weeks: {len(flags)} | late share: {late_share:.1%} | upside: {upside:.2f}")


if __name__ == "__main__":
    run()
