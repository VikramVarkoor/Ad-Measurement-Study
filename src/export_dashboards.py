"""Phase 8: export the dashboard feeds: the same tables for both BI tools.

Tableau Public and Looker Studio are point-and-click tools, so the publishing
step is manual; this script guarantees both tools read EXACTLY the tables the
pipeline produced, and dashboards/README.md walks through the build.
"""
from __future__ import annotations

import shutil

from . import paths

FEEDS = {
    "campaign_kpis.csv": "campaign_rollup.csv",
    "ad_kpis.csv": "ad_kpis.csv",
    "segment_cuts.csv": "segment_cuts.csv",
    "weekly_monitor.csv": "weekly_ecom.csv",
    "monitor_flags.csv": "monitor_flags.csv",
    "delay_vs_review.csv": "delay_vs_review.csv",
    "lift_results.csv": "lift_results.csv",
    "meta_studies.csv": "meta_studies.csv",
}


def run() -> None:
    for out_name, src_name in FEEDS.items():
        shutil.copy(paths.RESULTS / src_name, paths.DASHBOARDS / out_name)
    print(f"exported {len(FEEDS)} feeds to dashboards/")


if __name__ == "__main__":
    run()
