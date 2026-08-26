#!/usr/bin/env -S uv run --script
#
# /// script
# dependencies = [
#   "pandas",
# ]
# ///
"""Task 07: observed-vs-observed redundancy analysis.

Computes Spearman correlation matrices among the candidate observed-effort
metrics, on raw pooled values and on within-fork percentile ranks. Uses ONLY
Task 07 outputs; never reads Task 05 predicted scores.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TASK_DIR = Path(__file__).resolve().parent.parent
OUT = TASK_DIR / "outputs"
RED = OUT / "redundancy"

METRIC_COLUMNS = [
    "days_cutoff_to_mainnet",
    "subst_revisions_after_cutoff",
    "normative_revisions_after_cutoff",
    "devnet_count",
    "devnet_span_days",
    "days_cutoff_to_first_devnet",
    "deps_final",
    "deps_after_cutoff",
    "inclusion_reversals",
    "days_cutoff_to_sfi",
]


def main() -> None:
    RED.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(OUT / "observed-metrics.csv")
    pct = pd.read_csv(OUT / "observed-metrics-withinfork-pct.csv")

    m_raw = raw[METRIC_COLUMNS].corr(method="spearman").round(3)
    m_pct = pct[METRIC_COLUMNS].corr(method="spearman").round(3)
    m_raw.to_csv(RED / "spearman-raw.csv")
    m_pct.to_csv(RED / "spearman-withinfork-pct.csv")

    counts = raw[METRIC_COLUMNS].notna().sum().rename("non_null_of_%d" % len(raw))
    counts.to_csv(RED / "non-null-counts.csv")

    # observed_effort_composite_v0: equal-weight mean of the within-fork
    # percentile ranks of one representative per effort construct group
    # (rework, integration, coordination). Delivery lead time is deliberately
    # excluded; see outputs/redundancy/redundancy-report.md. All three
    # components are non-null on every row.
    components = ["subst_revisions_after_cutoff", "devnet_count", "deps_final"]
    comp = pct[["fork", "eip", "cross_layer", "cohort", "censored"] + components].copy()
    comp["observed_effort_composite_v0"] = comp[components].mean(axis=1)
    for c in components:  # leave-one-out sensitivity variants
        others = [o for o in components if o != c]
        comp[f"composite_without_{c}"] = comp[others].mean(axis=1)
    comp.to_csv(OUT / "observed-effort-composite-v0.csv", index=False)

    pd.set_option("display.width", 200)
    print("Non-null counts (of %d rows):" % len(raw))
    print(counts.to_string(), "\n")
    print("Pooled Spearman (raw values, pairwise complete):")
    print(m_raw.to_string(), "\n")
    print("Spearman on within-fork percentile ranks:")
    print(m_pct.to_string(), "\n")
    print("Composite (top/bottom 5 of observed_effort_composite_v0):")
    ranked = comp.sort_values("observed_effort_composite_v0", ascending=False)
    show = ["fork", "eip", "observed_effort_composite_v0"] + components
    print(ranked[show].head(5).to_string(index=False))
    print("...")
    print(ranked[show].tail(5).to_string(index=False))


if __name__ == "__main__":
    main()
