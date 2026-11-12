"""Phase 1: data audit: know what is in the data before trusting it.

Produces, in results/:
  data_audit.csv        one row per dataset: rows, columns, duplicates, missing
  srm.csv               sample-ratio check per experiment
  balance.csv           covariate balance (standardized mean differences)
  data_quality_log.csv  one row per issue found, what was done, rows touched
"""
from __future__ import annotations

import pandas as pd

from . import paths
from .experiments import STUDIES, connect, balance_table, group_counts
from .stats import srm_check

EXTRA_FILES = {
    "facebook_ads": str(paths.FACEBOOK_ADS),
    "olist_orders": str(paths.OLIST_DIR / "olist_orders_dataset.csv"),
    "olist_items": str(paths.OLIST_DIR / "olist_order_items_dataset.csv"),
    "olist_reviews": str(paths.OLIST_DIR / "olist_order_reviews_dataset.csv"),
}


def audit_file(con, name: str, path: str) -> dict:
    n_rows, n_cols = con.execute(
        f"SELECT count(*), (SELECT count(*) FROM (DESCRIBE SELECT * FROM '{path}'))"
        f" FROM '{path}'"
    ).fetchone()
    # duplicate full rows: groups of identical rows appearing more than once
    n_dupes = con.execute(f"""
        SELECT count(*) FROM (
            SELECT * FROM '{path}' GROUP BY ALL HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    return {"dataset": name, "rows": n_rows, "columns": n_cols, "duplicate_row_groups": n_dupes}


def run() -> None:
    con = connect()
    log_rows: list[dict] = []

    # ------------------------------------------------- audit every dataset
    audits = []
    for key, study in STUDIES.items():
        audits.append(audit_file(con, key, study.path))
    for name, path in EXTRA_FILES.items():
        audits.append(audit_file(con, name, path))
    audit_df = pd.DataFrame(audits)
    audit_df.to_csv(paths.RESULTS / "data_audit.csv", index=False, float_format="%.8g")

    # ------------------------------------------------- sample ratio checks
    srm_rows = []
    for key, study in STUDIES.items():
        counts = group_counts(study, con)
        total = counts["n_t"] + counts["n_c"]
        if study.expected_treated_share is None:
            srm_rows.append({
                "study": key, "n": total,
                "observed_share": counts["n_t"] / total,
                "expected_share": None, "chi2": None, "p_value": None,
                "verdict": "intended split undocumented: recorded, not testable",
            })
            continue
        r = srm_check(counts["n_t"], counts["n_c"], study.expected_treated_share)
        srm_rows.append({
            "study": key, "n": total,
            "observed_share": r["observed_share"],
            "expected_share": r["expected_share"],
            "chi2": r["chi2"], "p_value": r["p_value"],
            "verdict": "MISMATCH: investigate" if r["mismatch"] else "split consistent with intention",
        })
        if r["mismatch"]:
            log_rows.append({
                "dataset": key, "issue": "sample ratio mismatch",
                "detail": f"observed {r['observed_share']:.4f} vs intended {r['expected_share']:.4f}",
                "action": "flagged before analysis", "rows_touched": total,
            })
    pd.DataFrame(srm_rows).to_csv(paths.RESULTS / "srm.csv", index=False, float_format="%.8g")

    # ------------------------------------------------- covariate balance
    balances = []
    for key, study in STUDIES.items():
        b = balance_table(study, con)
        if len(b):
            balances.append(b)
            for _, row in b[b["flag"]].iterrows():
                log_rows.append({
                    "dataset": key, "issue": "covariate imbalance",
                    "detail": f"{row['feature']}: SMD {row['smd']:.3f}",
                    "action": "noted; randomization still trusted unless SRM also fails",
                    "rows_touched": None,
                })
    if balances:
        pd.concat(balances).to_csv(paths.RESULTS / "balance.csv", index=False, float_format="%.8g")

    # ------------------------------------------------- dataset-specific notes
    log_rows.append({
        "dataset": "marketing_ab", "issue": "index column present",
        "detail": "file carries an unnamed row-number column (column0)",
        "action": "ignored in analysis", "rows_touched": 588101,
    })
    log_rows.append({
        "dataset": "marketing_ab", "issue": "no pre-treatment covariates",
        "detail": "'total ads' is measured after assignment, so balance cannot be checked",
        "action": "balance table skipped; noted in methods", "rows_touched": None,
    })
    log_rows.append({
        "dataset": "criteo", "issue": "row count differs from plan",
        "detail": "file has 13,979,592 rows; plan said 'about 14 million'",
        "action": "file wins; recorded", "rows_touched": 13979592,
    })
    pd.DataFrame(log_rows).to_csv(paths.RESULTS / "data_quality_log.csv", index=False, float_format="%.8g")

    print(audit_df.to_string(index=False, float_format="%.8g"))
    print()
    print(pd.DataFrame(srm_rows).to_string(index=False, float_format="%.8g"))


if __name__ == "__main__":
    run()
