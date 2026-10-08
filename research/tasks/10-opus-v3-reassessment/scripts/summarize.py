#!/usr/bin/env python3
"""Freeze Task 10 assessment hashes and render the retrospective and prospective summaries.

Refuses to run unless every package has a valid assessment. Writes, per tree:
`outputs/assessment-manifest.yaml`, `outputs/summary.yaml` and `outputs/summary.md`.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import common
from common import InputError, file_sha256, load_yaml, rel, yaml_bytes
from engine_adapter import REPO_ROOT, TASK_ROOT
from validate import cases, validate


TASK04B = REPO_ROOT / "research" / "tasks" / "04b-fork-evaluation-cutoffs" / "outputs" / "forks"
TASK05_OUTPUTS = REPO_ROOT / "research" / "tasks" / "05-retrospective-complexity-assignment" / "outputs" / "fork-eips"


def row(case: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    engine = record["provenance"]["engine"]
    return {
        "eip": case["number"],
        "title": record["eip"]["title"],
        "score": record["totals"]["primary_score"],
        "tier": record["totals"]["complexity_tier"],
        "overall_confidence": record["overall_confidence"],
        "under_specified": record["under_specification"]["present"],
        "plausible_total_range": record["under_specification"]["plausible_total_range"],
        "cross_eip_bonus": next(item for item in record["criteria"] if item["id"] == common.XEIP)["bonus"],
        "assessment_path": rel(case["output"]),
        "duration_ms": engine["duration_ms"],
        "total_cost_usd": engine["total_cost_usd"],
    }


def freeze(selected: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "assessment_count": len(selected),
        "assessments": [
            {
                "key": case["key"],
                "assessment_path": rel(case["output"]),
                "assessment_sha256": file_sha256(case["output"]),
                "raw_path": rel(case["raw"]),
                "raw_sha256": file_sha256(case["raw"]),
            }
            for case in selected
        ],
    }


def run_statistics(records: list[dict[str, Any]]) -> dict[str, Any]:
    engines = [item["provenance"]["engine"] for item in records]
    durations = sorted(item["duration_ms"] / 60000 for item in engines)
    return {
        "calls": len(engines),
        "claude_code_versions": sorted({item["claude_code_version"] for item in engines}),
        "total_cost_usd": round(sum(item["total_cost_usd"] for item in engines), 2),
        "median_minutes": round(durations[len(durations) // 2], 1),
        "max_minutes": round(durations[-1], 1),
    }


def retrospective(selected: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    records = {case["key"]: load_yaml(case["output"]) for case in selected}
    forks = []
    for fork in common.config()["retrospective"]["forks"]:
        cutoff = load_yaml(TASK04B / f"{fork}.yaml")
        cohort = {entry["number"]: entry["cohort"] for entry in cutoff["eips"]}
        rows = []
        for case in selected:
            if case["fork"] != fork:
                continue
            item = row(case, records[case["key"]])
            item["scope_timing"] = "included_at_cutoff" if cohort[case["number"]] == "forecastable_at_cutoff" else "added_after_cutoff"
            v2 = load_yaml(TASK05_OUTPUTS / fork / f"eip-{case['number']}.yaml")["totals"]["primary_score"]
            item["task05_v2_score"] = v2
            rows.append(item)
        if {item["eip"] for item in rows} != set(cohort):
            raise InputError(f"{fork}: Task 10 assessments do not match the Task 04b cohort")
        at_cutoff = [item for item in rows if item["scope_timing"] == "included_at_cutoff"]
        forks.append(
            {
                "fork": fork,
                "cutoff_source": rel(TASK04B / f"{fork}.yaml"),
                "at_cutoff_eips": len(at_cutoff),
                "at_cutoff_score_sum": sum(item["score"] for item in at_cutoff),
                "final_scope_eips": len(rows),
                "final_scope_score_sum": sum(item["score"] for item in rows),
                "task05_v2_at_cutoff_score_sum": sum(item["task05_v2_score"] for item in at_cutoff),
                "eips": rows,
            }
        )
    summary = {
        "schema_version": 1,
        "task_id": common.TASK_ID,
        "mode": "retrospective",
        "evaluation": "claude-opus-5-5 · checklist revision 3",
        "assessments": len(selected),
        "tiers": dict(Counter(item["tier"] for fork in forks for item in fork["eips"])),
        "run_statistics": run_statistics(list(records.values())),
        "forks": forks,
    }
    lines = [
        "# Task 10 retrospective summary: Opus 5.5 · checklist revision 3",
        "",
        "Fork totals use the Task 04b at-cutoff cohorts. v2 is the Task 05 GPT-5.6 total for the same EIPs; revisions are not interchangeable.",
        "",
        "| Fork | At-cutoff EIPs | v3 at cutoff | v2 at cutoff | Final-scope EIPs | v3 final scope |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines += [
        f"| {common.FORK_NAMES[item['fork']]} | {item['at_cutoff_eips']} | {item['at_cutoff_score_sum']} | "
        f"{item['task05_v2_at_cutoff_score_sum']} | {item['final_scope_eips']} | {item['final_scope_score_sum']} |"
        for item in forks
    ]
    lines += ["", "| Fork | EIP | v3 | Tier | v2 | Scope |", "| --- | ---: | ---: | --- | ---: | --- |"]
    lines += [
        f"| {fork['fork']} | {item['eip']} | {item['score']} | {item['tier']} | {item['task05_v2_score']} | {item['scope_timing']} |"
        for fork in forks
        for item in fork["eips"]
    ]
    return summary, "\n".join(lines) + "\n"


def prospective(selected: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    settings = common.config()["prospective"]
    review = load_yaml(TASK_ROOT / "prospective" / "inputs" / "cohort-review.yaml")
    by_number = {case["number"]: case for case in selected}
    records = {case["number"]: load_yaml(case["output"]) for case in selected}
    entries, not_applicable = [], []
    for entry in review["entries"]:
        base = {"eip": entry["eip"], "title": entry["canonical_title"], "eip_8081_list": entry["eip_8081_list"],
                "affected_layers": entry["affected_layers"], "review_status": entry["review"]["status"]}  # fmt: skip
        if entry["disposition"] == "score_el_rubric":
            if entry["eip"] not in by_number:
                raise InputError(f"EIP-{entry['eip']} has no assessment")
            entries.append(base | row(by_number[entry["eip"]], records[entry["eip"]]))
        else:
            not_applicable.append(base | {"status": "not_applicable_to_el_rubric", "rationale": entry["rationale"]})
    if len(entries) != len(selected):
        raise InputError("Prospective assessments differ from the scored cohort-review entries")
    scenarios = {}
    for name, lists in (("SFI", ["SFI"]), ("SFI+CFI", ["SFI", "CFI"]), ("SFI+CFI+PFI", ["SFI", "CFI", "PFI"])):
        chosen = [item for item in entries if item["eip_8081_list"] in lists]
        scenarios[name] = {
            "scored_eips": len(chosen),
            "not_applicable_eips": sum(item["eip_8081_list"] in lists for item in not_applicable),
            "score_sum": sum(item["score"] for item in chosen),
        }
    summary = {
        "schema_version": 1,
        "task_id": common.TASK_ID,
        "mode": "prospective",
        "evaluation": "claude-opus-5-5 · checklist revision 3",
        "snapshot_id": settings["snapshot_id"],
        "eips_commit": settings["eips_commit"],
        "information_cutoff_at": settings["eips_committed_at"],
        "population": {"entries": len(review["entries"]), "scored": len(entries), "not_applicable": len(not_applicable)},
        "scenarios": scenarios,
        "tiers": dict(Counter(item["tier"] for item in entries)),
        "run_statistics": run_statistics(list(records.values())),
        "scored_eips": entries,
        "not_applicable_eips": not_applicable,
        "caveats": [
            "EL-rubric totals cover execution-layer testing work only; consensus-only and informational entries have no score, not a score of zero.",
            "EIP-8081's lists are still changing; a total describes one snapshot, not the eventual Hegotá scope.",
            "Overlapping EIPs and split proposals can double count or hide shared work.",
            "Seven dispositions added since Task 08 await owner review.",
        ],
    }
    lines = [
        "# Task 10 prospective summary: Hegotá at EIPs 6dac5e7, Opus 5.5 · checklist revision 3",
        "",
        "| Scenario | Scored EIPs | Not applicable | EL-rubric total |",
        "| --- | ---: | ---: | ---: |",
    ]
    lines += [f"| {name} | {item['scored_eips']} | {item['not_applicable_eips']} | {item['score_sum']} |" for name, item in scenarios.items()]
    lines += ["", "| List | EIP | Title | Score | Tier |", "| --- | ---: | --- | ---: | --- |"]
    lines += [f"| {item['eip_8081_list']} | {item['eip']} | {item['title']} | {item['score']} | {item['tier']} |" for item in entries]
    lines += [f"| {item['eip_8081_list']} | {item['eip']} | {item['title']} | N/A | — |" for item in not_applicable]
    return summary, "\n".join(lines) + "\n"


def main() -> int:
    every = cases()
    missing = [case["key"] for case in every if not case["output"].is_file()]
    if missing:
        raise InputError(f"Missing assessments: {missing}")
    for case in every:
        validate(case)
    for mode, render in (("retrospective", retrospective), ("prospective", prospective)):
        selected = [case for case in every if case["mode"] == mode]
        outputs = TASK_ROOT / mode / "outputs"
        (outputs / "assessment-manifest.yaml").write_bytes(yaml_bytes({"task_id": common.TASK_ID, "mode": mode, **freeze(selected)}))
        summary, markdown = render(selected)
        (outputs / "summary.yaml").write_bytes(yaml_bytes(summary))
        (outputs / "summary.md").write_text(markdown, encoding="utf-8")
        print(f"summarized {mode}: {len(selected)} assessments")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as error:
        raise SystemExit(f"input error: {error}") from error
