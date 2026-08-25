#!/usr/bin/env python3
"""Validate Task 04b fork cutoff and cohort records."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import yaml


TASK_ID = "04b-fork-evaluation-cutoffs"
TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK01_ROOT = REPO_ROOT / "research" / "tasks" / "01-fork-eip-history"
TASK04_ROOT = REPO_ROOT / "research" / "tasks" / "04-complexity-assessment-ref-selection"
OUTPUT_ROOT = TASK_ROOT / "outputs" / "forks"
FORKS = ("shanghai", "cancun", "prague", "osaka", "amsterdam")
COHORTS = {"forecastable_at_cutoff", "late_scope"}
TIMING_RELATIONS = {
    "at_or_before_cutoff",
    "after_cutoff",
    "cutoff_decision_recorded_after",
}
LATE_CLASSES = {
    "derived_companion",
    "independent_addition",
    "ancillary_or_non_consensus",
    "optional",
    "unresolved",
}
ATTRIBUTION_STATUSES = {
    "evidence_backed",
    "project_owner_hypothesis",
    "research_hypothesis",
    "not_attributed",
}


class ValidationError(RuntimeError):
    """Raised when a Task 04b record violates its contract."""


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"expected YAML mapping: {path}")
    return value


def bounds(value: str) -> tuple[datetime, datetime]:
    if len(value) == 10:
        day = date.fromisoformat(value)
        return datetime.combine(day, time.min, UTC), datetime.combine(day, time.max, UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValidationError(f"timestamp lacks UTC offset: {value}")
    instant = parsed.astimezone(UTC)
    return instant, instant


def resolve(repo_path: str) -> Path:
    path = REPO_ROOT / repo_path
    if not path.exists():
        raise ValidationError(f"missing referenced path: {repo_path}")
    return path


def source_ids(registry: dict[str, Any]) -> set[str]:
    return {str(source["id"]) for source in registry["sources"]}


def validate_fork(fork: str) -> dict[str, Any]:
    path = OUTPUT_ROOT / f"{fork}.yaml"
    record = load_yaml(path)
    if record.get("schema_version") != 1 or record.get("task_id") != TASK_ID:
        raise ValidationError(f"identity mismatch: {path}")
    if record.get("fork_id") != fork:
        raise ValidationError(f"fork mismatch: {path}")

    inputs = record["inputs"]
    relation_dir = resolve(inputs["task01_fork_eip_dir"])
    registry_path = resolve(inputs["task01_source_registry"])
    ref_dir = resolve(inputs["task04_ref_dir"])
    resolve(inputs["task01_fork_record"])
    resolve(inputs["task03_fork_input"])
    registry_ids = source_ids(load_yaml(registry_path))
    missing_cutoff_sources = set(record["cutoff"]["source_ids"]) - registry_ids
    if missing_cutoff_sources:
        raise ValidationError(
            f"unknown cutoff source IDs for {fork}: {sorted(missing_cutoff_sources)}"
        )

    cutoff = record["cutoff"]
    cutoff_start, cutoff_end = bounds(str(cutoff["effective_at"]))
    _, recorded_end = bounds(str(cutoff["recorded_at"]))
    expected_precision = "day" if len(str(cutoff["effective_at"])) == 10 else "instant"
    if cutoff["precision"] != expected_precision:
        raise ValidationError(f"cutoff precision mismatch for {fork}")
    if recorded_end < cutoff_start:
        raise ValidationError(f"recorded cutoff predates effective cutoff for {fork}")

    relations: dict[int, dict[str, Any]] = {}
    for relation_path in sorted(relation_dir.glob("eip-*.yaml")):
        relation = load_yaml(relation_path)
        if "execution" in relation["eip"]["layers"]:
            relations[int(relation["eip"]["number"])] = relation

    refs: dict[int, dict[str, Any]] = {}
    for ref_path in sorted(ref_dir.glob("eip-*.yaml")):
        ref = load_yaml(ref_path)
        number = int(ref["eip"]["number"])
        if ref["review"]["status"] != "approved":
            raise ValidationError(f"Task 04 ref is not approved: {fork}/EIP-{number}")
        refs[number] = ref
    if set(refs) != set(relations):
        raise ValidationError(f"Task 01/04 inventory mismatch for {fork}")

    entries = record["eips"]
    entry_numbers = [int(entry["number"]) for entry in entries]
    if len(entry_numbers) != len(set(entry_numbers)):
        raise ValidationError(f"duplicate EIP in {fork}")
    if set(entry_numbers) != set(refs):
        raise ValidationError(
            f"Task 04b inventory mismatch for {fork}: "
            f"missing={sorted(set(refs) - set(entry_numbers))}, "
            f"extra={sorted(set(entry_numbers) - set(refs))}"
        )

    counts = Counter()
    late_details: list[dict[str, Any]] = []
    for entry in entries:
        number = int(entry["number"])
        relation = relations[number]
        ref = refs[number]
        if entry["title"] != relation["eip"]["title"] or entry["title"] != ref["eip"]["title"]:
            raise ValidationError(f"title mismatch for {fork}/EIP-{number}")
        if resolve(entry["task04_record"]).resolve() != (ref_dir / f"eip-{number}.yaml").resolve():
            raise ValidationError(f"Task 04 path mismatch for {fork}/EIP-{number}")
        if str(entry["information_cutoff_at"]) != str(ref["selection"]["information_cutoff_at"]):
            raise ValidationError(f"information cutoff mismatch for {fork}/EIP-{number}")
        cohort = entry["cohort"]
        if cohort not in COHORTS:
            raise ValidationError(f"unknown cohort for {fork}/EIP-{number}: {cohort}")
        counts[cohort] += 1

        event_matches = [
            event
            for event in relation["inclusion_history"]["events"]
            if event["id"] == entry["scope_basis_event_id"]
        ]
        if len(event_matches) != 1:
            raise ValidationError(f"scope event does not resolve for {fork}/EIP-{number}")
        event = event_matches[0]
        if str(event["occurred_at"]) != str(entry["scope_basis_occurred_at"]):
            raise ValidationError(f"scope event timestamp mismatch for {fork}/EIP-{number}")
        event_start, event_end = bounds(str(event["occurred_at"]))
        timing = entry["timing_relation"]
        if timing not in TIMING_RELATIONS:
            raise ValidationError(f"unknown timing relation for {fork}/EIP-{number}")
        if timing == "at_or_before_cutoff" and event_start > cutoff_end:
            raise ValidationError(f"pre-cutoff event occurs late for {fork}/EIP-{number}")
        if timing == "after_cutoff" and event_end <= cutoff_end:
            raise ValidationError(f"late event does not occur late for {fork}/EIP-{number}")
        if timing == "cutoff_decision_recorded_after" and not (
            event_start > cutoff_end and event_end <= recorded_end
        ):
            raise ValidationError(f"recording exception out of range for {fork}/EIP-{number}")

        late = entry.get("late_scope")
        if cohort == "forecastable_at_cutoff":
            if late is not None or timing == "after_cutoff":
                raise ValidationError(f"forecastable entry marked late for {fork}/EIP-{number}")
        else:
            if not isinstance(late, dict) or timing != "after_cutoff":
                raise ValidationError(f"late entry lacks late metadata for {fork}/EIP-{number}")
            if late["classification"] not in LATE_CLASSES:
                raise ValidationError(f"unknown late class for {fork}/EIP-{number}")
            if late["attribution_status"] not in ATTRIBUTION_STATUSES:
                raise ValidationError(f"unknown attribution status for {fork}/EIP-{number}")
            missing_sources = set(late.get("source_ids", [])) - registry_ids
            if missing_sources:
                raise ValidationError(
                    f"unknown late source IDs for {fork}/EIP-{number}: {sorted(missing_sources)}"
                )
            for parent in late.get("attributable_to_eips", []):
                global_history = TASK01_ROOT / "outputs" / "eips" / f"eip-{int(parent)}.yaml"
                if not global_history.is_file():
                    raise ValidationError(
                        f"attribution parent EIP-{parent} missing for {fork}/EIP-{number}"
                    )
            late_details.append(
                {
                    "eip": number,
                    "classification": late["classification"],
                    "attribution_status": late["attribution_status"],
                    "attributable_to_eips": late.get("attributable_to_eips", []),
                }
            )

    summary = record["summary"]
    expected_summary = {
        "execution_affecting_eips": len(entries),
        "forecastable_at_cutoff": counts["forecastable_at_cutoff"],
        "late_scope": counts["late_scope"],
    }
    if summary != expected_summary:
        raise ValidationError(f"summary mismatch for {fork}: {summary} != {expected_summary}")

    review = record["review"]
    if review["status"] not in {"proposed", "approved"}:
        raise ValidationError(f"invalid review state for {fork}")
    if review["status"] == "approved":
        if not review.get("reviewer") or not review.get("reviewed_at"):
            raise ValidationError(f"approved cutoff lacks review metadata for {fork}")
        date.fromisoformat(review["reviewed_at"])
    elif review.get("reviewer") is not None or review.get("reviewed_at") is not None:
        raise ValidationError(f"proposed cutoff has reviewer metadata for {fork}")

    return {
        "cutoff": cutoff["effective_at"],
        "recorded_at": cutoff["recorded_at"],
        "review_status": review["status"],
        **expected_summary,
        "late_eips": late_details,
    }


def main() -> None:
    policy = load_yaml(TASK_ROOT / "outputs" / "aggregation-policy.yaml")
    if policy.get("task_id") != TASK_ID or policy.get("policy_id") != "fork-aggregation-cohorts-v1":
        raise ValidationError("aggregation policy identity mismatch")
    actual_files = {path.stem for path in OUTPUT_ROOT.glob("*.yaml")}
    if actual_files != set(FORKS):
        raise ValidationError(
            f"fork output set mismatch: missing={sorted(set(FORKS)-actual_files)}, "
            f"extra={sorted(actual_files-set(FORKS))}"
        )
    summary = {fork: validate_fork(fork) for fork in FORKS}
    print(json.dumps({"task_id": TASK_ID, "forks": summary}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
