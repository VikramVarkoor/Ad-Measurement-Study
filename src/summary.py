"""Stretch goal: a plain-English findings summary whose every number is
machine-verified against the results tables.

The summary is generated from results/*.csv, and each number it states
is registered as a claim (value + source file + source column). The
verifier (src/verify_summary.py) then re-reads the results and checks
every claim, and sweeps the text for any number that was never
registered. A wrong or unregistered number fails the build.

If GROQ_API_KEY is set, the draft is additionally rephrased by a
free-tier LLM and the rephrased text goes through the same verification;
without the key the deterministic draft is used as is.

Outputs: reports/findings_summary.md, reports/summary_claims.csv.
"""
from __future__ import annotations

import pandas as pd

from . import paths


class Claims:
    def __init__(self):
        self.rows = []

    def n(self, value, text: str, source: str, column: str) -> str:
        """Register a number and return its text form for the template."""
        self.rows.append({"text": text, "value": float(value),
                          "source": source, "column": column})
        return text

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def build_summary() -> tuple[str, pd.DataFrame]:
    c = Claims()
    lift = pd.read_csv(paths.RESULTS / "lift_results.csv")
    meta = pd.read_csv(paths.RESULTS / "meta_results.csv")
    up = pd.read_csv(paths.RESULTS / "uplift_summary.csv")
    dvr = pd.read_csv(paths.RESULTS / "delay_vs_review.csv")

    re_row = meta[meta.model.str.startswith("random")].iloc[0]
    crit = lift[lift.study == "criteo"].iloc[0]
    primary = lift[lift.kind == "primary"]
    up_c = up[up.study == "criteo"].iloc[0]
    up_h = up[up.study == "hillstrom"].iloc[0]
    on_time = dvr[dvr.delay_bucket.str.contains("on time")].iloc[0]
    late = dvr[dvr.delay_bucket.str.contains(">3")].iloc[0]

    users_m = (primary.n_treated.sum() + primary.n_control.sum()) / 1e6

    text = f"""# Findings summary

Generated from the results tables; every number below is
machine-verified by `src/verify_summary.py`.

## What marketing caused

Across {c.n(round(users_m, 1), f"{users_m:.1f}", "lift_results.csv",
"n_treated+n_control")} million users in six randomized experiments,
every treatment produced a real lift. Pooling the six studies with a
random-effects model gives a risk ratio of
{c.n(round(re_row.rr, 2), f"{re_row.rr:.2f}", "meta_results.csv", "rr")}
(95% CI {c.n(round(re_row.ci_low, 2), f"{re_row.ci_low:.2f}",
"meta_results.csv", "ci_low")} to
{c.n(round(re_row.ci_high, 2), f"{re_row.ci_high:.2f}",
"meta_results.csv", "ci_high")}), with an I-squared of
{c.n(round(re_row.I2 * 100, 1), f"{re_row.I2*100:.1f}",
"meta_results.csv", "I2")}%: the studies genuinely disagree, so no
single pooled number transfers to a new channel.

The largest experiment, Criteo display advertising, moved conversion
from {c.n(round(crit.rate_control * 100, 3), f"{crit.rate_control*100:.3f}",
"lift_results.csv", "rate_control")}% in the control group to
{c.n(round(crit.rate_treated * 100, 3), f"{crit.rate_treated*100:.3f}",
"lift_results.csv", "rate_treated")}% in the treated group, an absolute
lift of {c.n(round(crit.abs_lift_pp, 2), f"{crit.abs_lift_pp:.2f}",
"lift_results.csv", "abs_lift_pp")} percentage points.

## Who to target

Ranking users by predicted uplift concentrates the effect: messaging
the top 20% keeps
{c.n(round(up_c.share_kept_top20 * 100, 0),
f"{up_c.share_kept_top20*100:.0f}", "uplift_summary.csv",
"share_kept_top20")}% of the incremental conversions on Criteo
(held-out data). On the much smaller Hillstrom test the model keeps
only {c.n(round(up_h.share_kept_top20 * 100, 0),
f"{up_h.share_kept_top20*100:.0f}", "uplift_summary.csv",
"share_kept_top20")}%, barely above random, and is reported as weak.

## The e-commerce diagnosis

On the Olist marketplace, orders delivered more than three days late
average {c.n(round(late.avg_review_score, 2),
f"{late.avg_review_score:.2f}", "delay_vs_review.csv",
"avg_review_score")} stars against
{c.n(round(on_time.avg_review_score, 2),
f"{on_time.avg_review_score:.2f}", "delay_vs_review.csv",
"avg_review_score")} stars for on-time orders. This is an association,
not a cause: no experiment randomized lateness.
"""
    return text, c.frame()


def _groq_rephrase(draft: str) -> str | None:
    """Optional free-tier LLM pass; returns None if no key or on error."""
    import json
    import os
    import urllib.request
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    body = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system",
             "content": "Rephrase this findings summary to read more "
                        "naturally. Keep EVERY number exactly as written, "
                        "keep the markdown headings, change nothing "
                        "factual."},
            {"role": "user", "content": draft},
        ],
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            out = json.load(resp)
        return out["choices"][0]["message"]["content"]
    except Exception as exc:  # fall back to the deterministic draft
        print(f"groq rephrase skipped: {exc}")
        return None


def run() -> None:
    text, claims = build_summary()
    rephrased = _groq_rephrase(text)
    if rephrased is not None:
        text = rephrased
    (paths.REPORTS / "findings_summary.md").write_text(text)
    claims.to_csv(paths.REPORTS / "summary_claims.csv", index=False,
                  float_format="%.8g")
    from .verify_summary import verify
    report = verify()
    print(report.to_string(index=False))


if __name__ == "__main__":
    run()
