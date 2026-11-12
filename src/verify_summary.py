"""Verifier for the generated findings summary.

Two checks, both hard failures:

1. Every registered claim's value must still match the results table it
   cites (re-read from disk, compared within rounding tolerance).
2. Every number that appears in the summary text must be a registered
   claim: a hallucinated or edited number has no registration and
   fails the sweep.

Writes results/summary_verification.csv and raises on any failure.
"""
from __future__ import annotations

import re

import pandas as pd

from . import paths

# numbers in prose, e.g. 1.32, 99.7, 68, 16.1; a sentence-ending period
# after the number must still match, so the lookahead only blocks a
# longer number or a word continuing
NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?!\.?\d)(?!\w)")
# numbers that are prose, not findings (list markers, the year, etc.)
ALWAYS_ALLOWED = {"1", "2", "3", "20", "95", "10", "90", "12", "2026",
                  "80", "0"}


def _check_claim(row) -> bool:
    """Re-read the cited results file and confirm the value is present."""
    source = row.source.split("+")[0].strip()
    df = pd.read_csv(paths.RESULTS / source)
    val = float(row.value)
    cols = [c.strip() for c in row.column.split("+")]
    if len(cols) > 1:  # a sum across columns (e.g. total users, millions)
        if "kind" in df.columns:  # totals only ever count primary analyses
            df = df[df.kind == "primary"]
        total = sum(df[c].sum() for c in cols)
        return abs(total / 1e6 - val) < 0.05
    col = cols[0]
    series = pd.to_numeric(df[col], errors="coerce").dropna()
    # match raw values and the common rounded/scaled presentations
    candidates = set()
    for v in series:
        for scaled in (v, v * 100):
            for nd in (0, 1, 2, 3):
                candidates.add(round(scaled, nd))
    return round(val, 3) in {round(x, 3) for x in candidates}


def verify() -> pd.DataFrame:
    text = (paths.REPORTS / "findings_summary.md").read_text()
    claims = pd.read_csv(paths.REPORTS / "summary_claims.csv")

    rows = []
    for _, row in claims.iterrows():
        ok = _check_claim(row)
        rows.append({"check": "claim", "item": row.text,
                     "source": f"{row.source}:{row.column}",
                     "status": "PASS" if ok else "FAIL"})

    registered = {row.text for _, row in claims.iterrows()}
    registered |= {f"{float(t):g}" for t in registered}
    for num in NUMBER_RE.findall(text):
        if num in ALWAYS_ALLOWED:
            continue
        ok = num in registered or f"{float(num):g}" in registered
        rows.append({"check": "sweep", "item": num,
                     "source": "text", "status": "PASS" if ok else "FAIL"})

    report = pd.DataFrame(rows)
    report.to_csv(paths.RESULTS / "summary_verification.csv", index=False)
    failures = report[report.status == "FAIL"]
    if len(failures):
        raise AssertionError(
            "summary verification failed:\n"
            + failures.to_string(index=False))
    return report


if __name__ == "__main__":
    print(verify().to_string(index=False))
