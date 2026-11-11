"""Registry of the randomized studies and DuckDB aggregate extraction.

Each study is described once: where the file is, what counts as treated, what
the pre-registered outcome is, and the intended treatment share where the
source documents one. Everything downstream (audit, lift, meta-analysis)
reads from this registry, so a definition can never drift between phases.

All heavy lifting happens inside DuckDB as GROUP BY aggregates: the 14M-row
Criteo file is never loaded into Python memory.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

from . import paths


@dataclass(frozen=True)
class Study:
    key: str
    label: str                      # honest description of the treatment
    path: str                       # csv/csv.gz DuckDB can read
    treated_expr: str               # SQL boolean: is this row treated?
    outcome_expr: str               # SQL 0/1: the pre-registered outcome
    expected_treated_share: float | None  # intended split, None if undocumented
    channel: str                    # display / email / sms / offer ...
    balance_features: tuple = field(default_factory=tuple)  # pre-treatment columns
    in_meta: bool = True            # passes the inclusion rules?
    notes: str = ""


STUDIES: dict[str, Study] = {
    "criteo": Study(
        key="criteo",
        label="Criteo display advertising",
        path=str(paths.CRITEO),
        treated_expr="treatment = 1",
        outcome_expr="conversion",
        expected_treated_share=0.85,   # documented in the Criteo paper
        channel="display ads",
        balance_features=tuple(f"f{i}" for i in range(12)),
        notes="Analysed by assignment (treatment), never by exposure.",
    ),
    "hillstrom": Study(
        key="hillstrom",
        label="Hillstrom e-mail (any e-mail vs none)",
        path=str(paths.HILLSTROM),
        treated_expr="segment <> 'No E-Mail'",
        outcome_expr="conversion",
        expected_treated_share=2 / 3,  # random thirds; two e-mail arms pooled
        channel="email",
        balance_features=("recency", "history", "mens", "womens", "newbie"),
        notes="Both e-mail arms share one control, so they are pooled into one study.",
    ),
    "marketing_ab": Study(
        key="marketing_ab",
        label="Kaggle Marketing A/B (ad vs PSA)",
        path=str(paths.MARKETING_AB),
        treated_expr='"test group" = \'ad\'',
        outcome_expr='CASE WHEN converted THEN 1 ELSE 0 END',
        expected_treated_share=0.96,   # split stated on the dataset page
        channel="display ads",
        balance_features=(),           # 'total ads' is post-treatment: not usable
        notes="Control saw a public service announcement, not nothing.",
    ),
    "lenta": Study(
        key="lenta",
        label="Lenta retail marketing communication",
        path=str(paths.LENTA),
        treated_expr="\"group\" = 'test'",
        outcome_expr="response_att",
        expected_treated_share=None,   # intended split not documented
        channel="retail communication",
        balance_features=("age", "months_from_register", "food_share_1m"),
        notes="Intended split undocumented; SRM not testable, observed share recorded.",
    ),
    "x5": Study(
        key="x5",
        label="X5 RetailHero SMS promotion",
        path=str(paths.X5_TRAIN),
        treated_expr="treatment_flg = 1",
        outcome_expr="target",
        expected_treated_share=0.50,   # competition used a 50/50 split
        channel="sms promotion",
        balance_features=(),           # train file carries only ids
        notes="Promotion, not advertising: labelled that way everywhere.",
    ),
    "megafon": Study(
        key="megafon",
        label="MegaFon telecom offer",
        path=str(paths.MEGAFON),
        treated_expr="treatment_group = 'treatment'",
        outcome_expr="conversion",
        expected_treated_share=None,   # intended split not documented
        channel="telecom offer",
        balance_features=tuple(f"X_{i}" for i in range(1, 51)),
        notes="Features are synthetic; outcome and assignment are from the uplift contest.",
    ),
}


def connect() -> duckdb.DuckDBPyConnection:
    """A connection tuned for an 8GB machine: capped memory, fewer threads."""
    con = duckdb.connect()
    con.execute("SET memory_limit='3GB'")
    con.execute("SET threads=4")
    con.execute("SET preserve_insertion_order=false")
    return con


def effective_path(study: Study) -> str:
    """Prefer a materialized Parquet copy (much faster than re-reading csv.gz)."""
    pq = paths.PROCESSED / f"{study.key}.parquet"
    return str(pq) if pq.exists() else study.path


def materialize(study_key: str = "criteo") -> None:
    """One-time conversion of a large csv.gz to Parquet in data/processed/."""
    study = STUDIES[study_key]
    pq = paths.PROCESSED / f"{study.key}.parquet"
    if pq.exists():
        return
    con = connect()
    con.execute(
        f"COPY (SELECT * FROM '{study.path}') TO '{pq}' (FORMAT PARQUET)"
    )


def group_counts(study: Study, con: duckdb.DuckDBPyConnection | None = None) -> dict:
    """Users and outcome events per arm, computed as a DuckDB aggregate."""
    con = con or connect()
    row = con.execute(f"""
        SELECT
            SUM(CASE WHEN {study.treated_expr} THEN 1 ELSE 0 END)                          AS n_t,
            SUM(CASE WHEN {study.treated_expr} THEN ({study.outcome_expr}) ELSE 0 END)     AS x_t,
            SUM(CASE WHEN NOT ({study.treated_expr}) THEN 1 ELSE 0 END)                    AS n_c,
            SUM(CASE WHEN NOT ({study.treated_expr}) THEN ({study.outcome_expr}) ELSE 0 END) AS x_c
        FROM '{effective_path(study)}'
    """).fetchone()
    n_t, x_t, n_c, x_c = (int(v) for v in row)
    return {"study": study.key, "n_t": n_t, "x_t": x_t, "n_c": n_c, "x_c": x_c}


def balance_table(study: Study, con: duckdb.DuckDBPyConnection | None = None):
    """Standardized mean difference per pre-treatment feature.

    SMD = (mean_t - mean_c) / sqrt((var_t + var_c) / 2); |SMD| > 0.1 is noted.
    Computed fully inside DuckDB so it works on the 14M-row file.
    """
    import pandas as pd

    if not study.balance_features:
        return pd.DataFrame()
    con = con or connect()
    # one scan of the file computing every feature's aggregates at once
    agg_cols = []
    for feat in study.balance_features:
        agg_cols += [
            f'AVG(CASE WHEN {study.treated_expr} THEN "{feat}" END) AS "mean_t__{feat}"',
            f'AVG(CASE WHEN NOT ({study.treated_expr}) THEN "{feat}" END) AS "mean_c__{feat}"',
            f'VAR_SAMP(CASE WHEN {study.treated_expr} THEN "{feat}" END) AS "var_t__{feat}"',
            f'VAR_SAMP(CASE WHEN NOT ({study.treated_expr}) THEN "{feat}" END) AS "var_c__{feat}"',
        ]
    wide = con.execute(
        f"SELECT {', '.join(agg_cols)} FROM '{effective_path(study)}'"
    ).df().iloc[0]
    df = pd.DataFrame([
        {
            "feature": feat,
            "mean_t": wide[f"mean_t__{feat}"],
            "mean_c": wide[f"mean_c__{feat}"],
            "var_t": wide[f"var_t__{feat}"],
            "var_c": wide[f"var_c__{feat}"],
        }
        for feat in study.balance_features
    ])
    pooled_sd = ((df["var_t"] + df["var_c"]) / 2) ** 0.5
    df["smd"] = (df["mean_t"] - df["mean_c"]) / pooled_sd
    df["flag"] = df["smd"].abs() > 0.1
    df.insert(0, "study", study.key)
    return df
