"""Fork summaries, criterion compositions, EIP index, compare index, and downloads."""

from __future__ import annotations

import csv
from typing import Any

from .common import (
    FORK_NAMES,
    FORK_ORDER,
    FORK_SHORT_NAMES,
    PROSPECTIVE_FORK,
    PUBLIC,
    RETROSPECTIVE_FORKS,
    SOURCE_HUMAN,
    SOURCE_LLM,
    STATUS_NOT_APPLICABLE,
    ASSESSMENT_STATUSES,
)
from .rubric import NOMINAL_MAXIMUM, REGISTRY_ORDER, RUBRIC_ORDER, TIER_THRESHOLDS


def composition(assessments: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum every criterion across the given scored assessments (all must share one rubric revision)."""
    totals: dict[str, dict[str, int]] = {}
    revisions = {item["rubric_revision"] for item in assessments}
    if len(revisions) > 1:
        raise ValueError("composition requires one rubric revision")
    for assessment in assessments:
        for criterion in assessment["criteria"]:
            bucket = totals.setdefault(criterion["id"], {"score_sum": 0, "eip_count": 0})
            bucket["score_sum"] += criterion["score"]
            if criterion["score"] > 0:
                bucket["eip_count"] += 1
    return {
        "assessment_count": len(assessments),
        "rubric_revision": next(iter(revisions)) if revisions else None,
        "score_sum": sum(item["score"] for item in assessments),
        "criteria": [
            {"id": criterion_id, **totals[criterion_id]}
            for criterion_id in REGISTRY_ORDER
            if criterion_id in totals
        ],
    }


def fork_summaries(
    occurrences: list[dict[str, Any]], assessments: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    summaries = []
    for fork in FORK_ORDER:
        fork_occurrences = [item for item in occurrences if item["fork"] == fork]
        primary = [
            assessments[item["llm"]["assessment_id"]]
            for item in fork_occurrences
            if item["llm"]["assessment_id"] is not None
        ]
        by_eip = {item["eip"]: item for item in primary}
        at_cutoff = [by_eip[item["eip"]] for item in fork_occurrences if item["scope_timing"] == "included_at_cutoff"]
        added_later = [by_eip[item["eip"]] for item in fork_occurrences if item["scope_timing"] == "added_after_cutoff"]
        human_counts = {status: 0 for status in ASSESSMENT_STATUSES}
        for item in fork_occurrences:
            human_counts[item["human"]["status"]] += 1
        human_scored = [item for item in fork_occurrences if item["human"]["assessment_id"] and assessments[item["human"]["assessment_id"]]["scored"]]
        summary: dict[str, Any] = {
            "fork": fork,
            "name": FORK_NAMES[fork],
            "short_name": FORK_SHORT_NAMES[fork],
            "mode": "prospective" if fork == PROSPECTIVE_FORK else "retrospective",
            "eip_count": len(fork_occurrences),
            "scored_count": len(primary),
            "not_applicable_count": len(fork_occurrences) - len(primary),
            "final_scope_score_sum": sum(item["score"] for item in primary),
            "human_coverage": {
                "status_counts": human_counts,
                "scored_count": len(human_scored),
                "comparable_count": sum(1 for item in fork_occurrences if item["comparison_ids"]),
            },
        }
        if fork == PROSPECTIVE_FORK:
            pfi = [item for item in primary if occurrence_status(fork_occurrences, item["eip"]) == "PFI"]
            summary.update(
                {
                    "at_cutoff_count": None,
                    "at_cutoff_score_sum": None,
                    "late_addition_count": None,
                    "late_addition_score_sum": None,
                    "score_sum": sum(item["score"] for item in primary),
                    "composition": {
                        "all_scored": composition(primary),
                        "pfi_only": composition(pfi),
                    },
                }
            )
        else:
            summary.update(
                {
                    "at_cutoff_count": len(at_cutoff),
                    "at_cutoff_score_sum": sum(item["score"] for item in at_cutoff),
                    "late_addition_count": len(added_later),
                    "late_addition_score_sum": sum(item["score"] for item in added_later),
                    "score_sum": sum(item["score"] for item in at_cutoff),
                    "composition": {
                        "at_cutoff": composition(at_cutoff),
                        "added_after_cutoff": composition(added_later),
                        "final_scope": composition(primary),
                    },
                }
            )
        summaries.append(summary)
    return summaries


def occurrence_status(occurrences: list[dict[str, Any]], eip: int) -> str | None:
    return next(item["snapshot_status"] for item in occurrences if item["eip"] == eip)


def eip_index(occurrences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group occurrences by EIP; the default fork is the latest retrospective fork, else the prospective one."""
    grouped: dict[int, list[dict[str, Any]]] = {}
    for occurrence in occurrences:
        grouped.setdefault(occurrence["eip"], []).append(occurrence)
    eips = []
    for eip in sorted(grouped):
        items = sorted(grouped[eip], key=lambda item: FORK_ORDER.index(item["fork"]))
        retrospective = [item for item in items if item["mode"] == "retrospective"]
        default = (retrospective or items)[-1]
        eips.append(
            {
                "eip": eip,
                "title": items[-1]["title"],
                "forks": [item["fork"] for item in items],
                "default_fork": default["fork"],
                "route": f"eips/{eip}/",
                "occurrences": items,
            }
        )
    return eips


def compare_index(
    assessments: dict[str, dict[str, Any]], eips: list[dict[str, Any]], criteria: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compact client-side payload for the shared EIP comparison view."""
    rows = []
    for assessment in sorted(assessments.values(), key=lambda item: item["id"]):
        order = RUBRIC_ORDER[assessment["rubric_revision"]]
        scores = {item["id"]: item["score"] for item in assessment["criteria"]}
        under = assessment.get("under_specification") or {}
        rows.append(
            {
                "id": assessment["id"],
                "eip": assessment["eip"],
                "fork": assessment["fork"],
                "source": assessment["source"],
                "rubric_revision": assessment["rubric_revision"],
                "role": assessment["role"],
                "status": assessment["status"],
                "scored": assessment["scored"],
                "score": assessment["score"],
                "tier": assessment["tier"],
                "scores": [scores.get(criterion_id) if criterion_id in order else None for criterion_id in REGISTRY_ORDER],
                "under_specified": bool(under.get("present")),
                "affected_criteria": list(under.get("affected_criteria") or []),
            }
        )
    return {
        "schema_version": "2.0.0",
        "criteria": [
            {"id": item["id"], "label": item["label"], "short_definition": item["short_definition"], "rubric_revisions": item["rubric_revisions"]}
            for item in criteria
        ],
        "rubrics": {str(revision): {"criteria": order, "tier_thresholds": TIER_THRESHOLDS[revision], "nominal_maximum": NOMINAL_MAXIMUM[revision]} for revision, order in RUBRIC_ORDER.items()},
        "forks": [{"fork": fork, "name": FORK_NAMES[fork], "short_name": FORK_SHORT_NAMES[fork]} for fork in FORK_ORDER],
        "eips": [
            {
                "eip": item["eip"],
                "title": item["title"],
                "forks": item["forks"],
                "default_fork": item["default_fork"],
                "snapshot_status": {occ["fork"]: occ["snapshot_status"] for occ in item["occurrences"] if occ["snapshot_status"]},
            }
            for item in eips
        ],
        "assessments": rows,
    }


def write_downloads(occurrences: list[dict[str, Any]], assessments: dict[str, dict[str, Any]]) -> None:
    root = PUBLIC / "downloads"
    root.mkdir(parents=True, exist_ok=True)
    fields = [
        "assessment_id", "mode", "fork", "eip", "title", "source", "rubric_revision", "role", "status", "scored",
        "score", "tier", "confidence", "under_specification", "scope_timing", "snapshot_status", "layers",
        "source_kind", "pull_request", "exclusion_kind", "rationale",
    ]
    rows: list[dict[str, Any]] = []
    for occurrence in occurrences:
        for assessment_id in occurrence["assessment_ids"]:
            assessment = assessments[assessment_id]
            record = assessment["provenance"]["source_record"]
            pull = record.get("pull_request")
            rows.append(
                {
                    "assessment_id": assessment["id"],
                    "mode": assessment["mode"],
                    "fork": assessment["fork"],
                    "eip": assessment["eip"],
                    "title": assessment["title"],
                    "source": assessment["source"],
                    "rubric_revision": assessment["rubric_revision"],
                    "role": assessment["role"],
                    "status": assessment["status"],
                    "scored": assessment["scored"],
                    "score": assessment["score"],
                    "tier": assessment["tier"],
                    "confidence": assessment["confidence"],
                    "under_specification": (assessment.get("under_specification") or {}).get("present"),
                    "scope_timing": occurrence["scope_timing"],
                    "snapshot_status": occurrence["snapshot_status"],
                    "layers": ";".join(occurrence["layers"]),
                    "source_kind": record["kind"],
                    "pull_request": pull["url"] if pull else None,
                    "exclusion_kind": None,
                    "rationale": None,
                }
            )
        if occurrence["llm"]["status"] == STATUS_NOT_APPLICABLE:
            rows.append(
                {
                    "assessment_id": None,
                    "mode": occurrence["mode"],
                    "fork": occurrence["fork"],
                    "eip": occurrence["eip"],
                    "title": occurrence["title"],
                    "source": SOURCE_LLM,
                    "rubric_revision": None,
                    "role": None,
                    "status": STATUS_NOT_APPLICABLE,
                    "scored": False,
                    "score": None,
                    "tier": None,
                    "confidence": None,
                    "under_specification": None,
                    "scope_timing": None,
                    "snapshot_status": occurrence["snapshot_status"],
                    "layers": ";".join(occurrence["layers"]),
                    "source_kind": None,
                    "pull_request": None,
                    "exclusion_kind": occurrence["llm"]["exclusion_kind"],
                    "rationale": occurrence["llm"]["rationale"],
                }
            )
    with (root / "complexity-assessments.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    criterion_fields = ["assessment_id", "fork", "eip", "source", "rubric_revision", "criterion", "score", "under_specified"]
    with (root / "criterion-scores.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=criterion_fields, lineterminator="\n")
        writer.writeheader()
        for assessment in sorted(assessments.values(), key=lambda item: item["id"]):
            for criterion in assessment["criteria"]:
                writer.writerow(
                    {
                        "assessment_id": assessment["id"],
                        "fork": assessment["fork"],
                        "eip": assessment["eip"],
                        "source": assessment["source"],
                        "rubric_revision": assessment["rubric_revision"],
                        "criterion": criterion["id"],
                        "score": criterion["score"],
                        "under_specified": criterion["under_specified"],
                    }
                )
