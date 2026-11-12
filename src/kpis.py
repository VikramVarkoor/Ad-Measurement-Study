"""Phase 2: run the campaign KPI layer and cross-check SQL against pandas.

Outputs in results/: ad_kpis.csv, campaign_rollup.csv, segment_cuts.csv,
ad_rank_in_campaign.csv, running_spend.csv, kpi_dictionary.csv,
kpi_crosscheck.csv (SQL totals vs pandas totals: must match exactly).

ROAS is reported only under a stated assumption (VALUE_PER_CONVERSION), and
every table that carries it says so in a column of its own.
"""
from __future__ import annotations

import pandas as pd

from . import paths
from .experiments import connect

VALUE_PER_CONVERSION = 50.0  # USD per approved conversion: an assumption, stated everywhere

KPI_DICTIONARY = [
    ("CTR", "clicks / impressions", "share (0–1)",
     "0 impressions -> undefined (NULL), never 0"),
    ("CPM", "spend / impressions * 1000", "USD per 1,000 impressions",
     "noisy below ~100k impressions; low_volume_flag marks those segments"),
    ("CPC", "spend / clicks", "USD per click",
     "0 clicks -> undefined (NULL)"),
    ("CVR (conversion rate)", "approved conversions / clicks", "share (0–1)",
     "base is CLICKS, stated; 0 clicks -> undefined"),
    ("CPA", "spend / approved conversions", "USD per conversion",
     "0 conversions -> undefined (NULL), never 0; ads with spend and no "
     "conversions have infinite effective CPA and rank last"),
    ("ROAS", f"approved conversions * {VALUE_PER_CONVERSION:.0f} / spend", "ratio",
     f"the data has no revenue column; {VALUE_PER_CONVERSION:.0f} USD per "
     "conversion is an assumption and every ROAS figure is labelled with it"),
    ("Absolute lift", "treated rate - control rate", "percentage points",
     "only meaningful in a randomized experiment"),
    ("Relative lift", "absolute lift / control rate", "percent",
     "undefined when the control rate is 0"),
    ("Incremental conversions", "absolute lift * treated group size", "conversions",
     "the extra conversions the treatment caused"),
    ("iCPA", "spend / incremental conversions", "USD per incremental conversion",
     "the honest CPA; needs an experiment, not just tracking"),
]


def run() -> None:
    con = connect()
    con.execute(
        f"CREATE OR REPLACE TABLE facebook_ads AS SELECT * FROM '{paths.FACEBOOK_ADS}'"
    )
    con.execute((paths.SQL / "kpis.sql").read_text())

    views = ["ad_kpis", "campaign_rollup", "ad_rank_in_campaign",
             "running_spend", "segment_cuts"]
    frames = {}
    for v in views:
        df = con.execute(f"SELECT * FROM {v}").df()
        # deterministic row order: DuckDB's parallel scans return rows in
        # whatever order the threads finish, which would churn the committed CSVs
        df = df.sort_values(by=list(df.columns)).reset_index(drop=True)
        frames[v] = df
        df.to_csv(paths.RESULTS / f"{v}.csv", index=False, float_format="%.8g")

    # ROAS under the stated assumption, at campaign level
    roll = frames["campaign_rollup"].copy()
    roll["value_per_conversion_assumed"] = VALUE_PER_CONVERSION
    roll["roas_assumed"] = roll["conversions"] * VALUE_PER_CONVERSION / roll["spend"]
    roll.to_csv(paths.RESULTS / "campaign_rollup.csv", index=False, float_format="%.8g")

    pd.DataFrame(
        KPI_DICTIONARY, columns=["metric", "formula", "unit", "edge_cases"]
    ).to_csv(paths.RESULTS / "kpi_dictionary.csv", index=False, float_format="%.8g")

    # ------------------------------------------------ cross-check vs pandas
    raw = pd.read_csv(paths.FACEBOOK_ADS)
    checks = []

    def check(name: str, sql_value: float, pandas_value: float) -> None:
        checks.append({
            "total": name,
            "sql": sql_value,
            "pandas": pandas_value,
            "diff": sql_value - pandas_value,
            "match": abs(sql_value - pandas_value) < 1e-9,
        })

    check("impressions", float(frames["campaign_rollup"]["impressions"].sum()),
          float(raw["Impressions"].sum()))
    check("clicks", float(frames["campaign_rollup"]["clicks"].sum()),
          float(raw["Clicks"].sum()))
    check("spend", float(frames["campaign_rollup"]["spend"].sum()),
          float(raw["Spent"].sum()))
    check("conversions", float(frames["campaign_rollup"]["conversions"].sum()),
          float(raw["Approved_Conversion"].sum()))
    check("overall CTR",
          float(frames["campaign_rollup"]["clicks"].sum()
                / frames["campaign_rollup"]["impressions"].sum()),
          float(raw["Clicks"].sum() / raw["Impressions"].sum()))

    checks_df = pd.DataFrame(checks)
    checks_df.to_csv(paths.RESULTS / "kpi_crosscheck.csv", index=False, float_format="%.8g")

    print(frames["campaign_rollup"].round(4).to_string(index=False, float_format="%.8g"))
    print()
    print(checks_df.to_string(index=False, float_format="%.8g"))
    if not checks_df["match"].all():
        raise SystemExit("SQL and pandas totals disagree: stop and find out why.")


if __name__ == "__main__":
    run()
