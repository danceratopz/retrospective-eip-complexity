#!/usr/bin/env python3
"""Extract METR's frontier 50% time-horizon series from a downloaded benchmark-results file.

    curl -sSfL https://metr.org/assets/benchmark_results_1_1.yaml -o /tmp/metr.yaml
    extract_frontier_series.py /tmp/metr.yaml --retrieved-at 2026-10-08T11:43:29Z

METR's file has no stated licence, so it is reference-only: only the extracted model, release date and
horizon values are committed, with the source URL, retrieval time and SHA-256 of the file they came from.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml


TASK_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = TASK_ROOT / "outputs" / "metr-frontier-horizon.yaml"
SOURCE_URL = "https://metr.org/assets/benchmark_results_1_1.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--retrieved-at", required=True)
    args = parser.parse_args()
    data = args.source.read_bytes()
    results = yaml.safe_load(data)
    if results.get("benchmark_name") != "METR-Horizon-v1.1":
        raise SystemExit("unexpected benchmark file")
    models = []
    for key, item in results["results"].items():
        p50 = item["metrics"]["p50_horizon_length"]
        models.append(
            {
                "model": key,
                "release_date": str(item["release_date"]),
                "is_sota": bool(item["metrics"].get("is_sota")),
                "p50_minutes": round(p50["estimate"], 2),
                "p50_ci_low_minutes": round(p50["ci_low"], 2),
                "p50_ci_high_minutes": round(p50["ci_high"], 2),
            }
        )
    models.sort(key=lambda row: (row["release_date"], row["model"]))
    # The frontier at a date is the highest horizon among models released on or before it.
    frontier, best = [], 0.0
    for row in models:
        if row["p50_minutes"] > best:
            best = row["p50_minutes"]
            frontier.append(row)
    record = {
        "schema_version": 1,
        "task_id": "11-ai-capability-context",
        "source": {
            "publisher": "METR",
            "benchmark": results["benchmark_name"],
            "url": SOURCE_URL,
            "retrieved_at": args.retrieved_at,
            "content_sha256": hashlib.sha256(data).hexdigest(),
            "redistribution": "reference_only",
            "note": "No licence is stated for the file; only extracted values are recorded here.",
        },
        "metric": "50% task-completion time horizon: the length of software task, in human working minutes, that the model completes with 50% success",
        "frontier_rule": "At a date, the frontier is the highest 50% horizon among models released on or before that date.",
        "frontier": frontier,
        "models": models,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    print(f"wrote {OUTPUT}: {len(frontier)} frontier steps from {len(models)} models")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
