#!/usr/bin/env python3
"""Build deterministic, sanitized publication records from frozen research data.

The adapter projects research records into one domain model:

    EIP -> occurrence (one fork context) -> assessments (source x rubric revision) -> criterion assessments

plus same-rubric Human-versus-LLM comparisons, fork criterion compositions, and a compact compare index.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from publication_adapter.aggregates import compare_index, eip_index, fork_summaries, write_downloads  # noqa: E402
from publication_adapter.charts import charts  # noqa: E402
from publication_adapter.common import (  # noqa: E402
    FORK_ORDER,
    PUBLIC,
    SOURCE_HUMAN,
    STATUS_NOT_AVAILABLE,
    VERSION,
    BuildError,
    Sanitizer,
    digest,
    write_json,
)
from publication_adapter.comparisons import build_comparisons  # noqa: E402
from publication_adapter.rubric import build_rubrics  # noqa: E402
from publication_adapter.sources import (  # noqa: E402
    load_amsterdam_human,
    load_hegota_human,
    load_prospective,
    load_retrospective,
)


HUMAN_NOT_PRODUCED_NOTE = "Human complexity assessments were not produced for this fork; only the LLM assessment exists."
HUMAN_NOT_PUBLISHED_NOTE = "The STEEL team did not publish a human checklist for this EIP in the Amsterdam assessment round."


def _human_summary(assessment: dict[str, Any] | None, *, status: str | None = None, note: str | None = None) -> dict[str, Any]:
    if assessment is None:
        return {
            "status": status or STATUS_NOT_AVAILABLE,
            "assessment_id": None,
            "score": None,
            "tier": None,
            "rubric_revision": None,
            "source_record": None,
            "other_candidates": [],
            "note": note,
        }
    return {
        "status": assessment["status"],
        "assessment_id": assessment["id"],
        "score": assessment["score"],
        "tier": assessment["tier"],
        "rubric_revision": assessment["rubric_revision"],
        "source_record": assessment["provenance"]["source_record"],
        "other_candidates": [],
        "note": None,
    }


def build() -> dict[str, Any]:
    criteria, rubrics, rubric_sources = build_rubrics()
    rubric_provenance = {int(key): value["source"] for key, value in rubrics.items()}

    retro_occurrences, retro_assessments, retro_sources = load_retrospective()
    pro_occurrences, pro_assessments, hegota_summary, pro_sources = load_prospective()
    amsterdam_assessments, task05c_comparisons, amsterdam_sources = load_amsterdam_human()
    titles = {item["eip"]: item["title"] for item in pro_occurrences}
    hegota_human, hegota_human_assessments, hegota_human_snapshot, hegota_human_sources = load_hegota_human(
        titles, {revision: {key: value for key, value in item.items() if key != "checklist_revision"} for revision, item in rubric_provenance.items()}
    )

    occurrences = retro_occurrences + pro_occurrences
    occurrences.sort(key=lambda item: (FORK_ORDER.index(item["fork"]), item["eip"]))
    if len(occurrences) != 95 or len(retro_occurrences) != 49 or len(pro_occurrences) != 46:
        raise BuildError("occurrence population mismatch")

    assessments: dict[str, dict[str, Any]] = {}
    for assessment in [*retro_assessments, *pro_assessments, *amsterdam_assessments, *hegota_human_assessments]:
        if assessment["id"] in assessments:
            raise BuildError(f"duplicate assessment id {assessment['id']}")
        assessments[assessment["id"]] = assessment

    by_occurrence: dict[str, list[dict[str, Any]]] = {}
    for assessment in assessments.values():
        by_occurrence.setdefault(f"{assessment['fork']}:{assessment['eip']}", []).append(assessment)
    for occurrence in occurrences:
        related = sorted(
            by_occurrence.get(occurrence["id"], []),
            key=lambda item: (item["source"] != "llm", -item["rubric_revision"]),
        )
        occurrence["assessment_ids"] = [item["id"] for item in related]
        human_items = [item for item in related if item["source"] == SOURCE_HUMAN]
        if occurrence["fork"] == "hegota":
            occurrence["human"] = hegota_human[occurrence["eip"]]
        elif occurrence["fork"] == "amsterdam":
            occurrence["human"] = _human_summary(human_items[0] if human_items else None, note=None if human_items else HUMAN_NOT_PUBLISHED_NOTE)
        else:
            if human_items:
                raise BuildError(f"unexpected human assessment for {occurrence['id']}")
            occurrence["human"] = _human_summary(None, note=HUMAN_NOT_PRODUCED_NOTE)
        if occurrence["human"]["assessment_id"] and occurrence["human"]["assessment_id"] not in occurrence["assessment_ids"]:
            raise BuildError(f"human assessment missing from occurrence {occurrence['id']}")
        occurrence["default_assessment_id"] = (
            occurrence["llm"]["assessment_id"] or occurrence["human"]["assessment_id"]
        )

    comparisons = build_comparisons(assessments, task05c_comparisons)
    for comparison in comparisons.values():
        occurrence = next(item for item in occurrences if item["id"] == f"{comparison['fork']}:{comparison['eip']}")
        occurrence["comparison_ids"].append(comparison["id"])
    amsterdam_pairs = [item for item in comparisons.values() if item["fork"] == "amsterdam"]
    if len(amsterdam_pairs) != 12:
        raise BuildError("Amsterdam must yield twelve same-rubric comparisons")

    forks = fork_summaries(occurrences, assessments)
    eips = eip_index(occurrences)
    hegota_summary["human_snapshot"] = hegota_human_snapshot

    chart_rows = [
        {
            "fork": item["fork"],
            "eip": item["eip"],
            "title": item["title"],
            "mode": item["mode"],
            "status": "scored" if item["llm"]["assessment_id"] else "not_applicable",
            "score": item["llm"]["score"],
            "tier": item["llm"]["tier"],
            "under_specification": item["llm"]["under_specified"],
            "scope_timing": item["scope_timing"],
            "snapshot_status": item["snapshot_status"],
        }
        for item in occurrences
    ]
    chart_paths, shipping_analysis, alignment_rows, chart_sources = charts(chart_rows)
    write_downloads(occurrences, assessments)

    payload = {
        "assessments": assessments,
        "charts": chart_paths,
        "comparisons": comparisons,
        "criteria": criteria,
        "eips": eips,
        "fork_shipping": shipping_analysis,
        "forks": forks,
        "hegota": hegota_summary,
        "human_llm": {"rows": alignment_rows},
        "release_state": "public",
        "rubrics": rubrics,
        "schema_version": VERSION,
    }
    index = compare_index(assessments, eips, criteria)
    sanitizer = Sanitizer()
    sanitizer.check(payload)
    sanitizer.check(index)
    write_json(PUBLIC / "publication.json", payload)
    write_json(PUBLIC / "compare-index.json", index)

    all_sources = rubric_sources + retro_sources + pro_sources + amsterdam_sources + hegota_human_sources + chart_sources
    unique_sources = {item["path"]: item for item in all_sources}
    manifest = {
        "generated_files": [],
        "schema_version": VERSION,
        "source_records": [unique_sources[key] for key in sorted(unique_sources)],
    }
    for path in sorted(PUBLIC.rglob("*")):
        if path.is_file() and path.name != "provenance.json":
            manifest["generated_files"].append({"path": path.relative_to(PUBLIC).as_posix(), "sha256": digest(path)})
    write_json(PUBLIC / "provenance.json", manifest)
    return {
        "occurrences": len(occurrences),
        "assessments": len(assessments),
        "comparisons": len(comparisons),
        "eips": len(eips),
        "sources": len(manifest["source_records"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Build twice and require byte-identical output")
    args = parser.parse_args()
    result = build()
    if args.check:
        before = {path.relative_to(PUBLIC): digest(path) for path in PUBLIC.rglob("*") if path.is_file()}
        build()
        after = {path.relative_to(PUBLIC): digest(path) for path in PUBLIC.rglob("*") if path.is_file()}
        if before != after:
            raise BuildError("publication adapter output is not deterministic")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as error:
        raise SystemExit(f"build error: {error}") from error
