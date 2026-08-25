#!/usr/bin/env python3
"""Compare frozen automated observations A/B with historical human observation C."""

from __future__ import annotations

import copy
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from common import (
    AUTOMATED_ROOT,
    COMPARISON_ROOT,
    CONTRACT_PATH,
    DATASET_MANIFEST_PATH,
    FREEZE_PATH,
    INVENTORY_PATH,
    PACKAGE_ROOT,
    REPO_ROOT,
    SUMMARY_PATH,
    TASK_ROOT,
    StudyError,
    load_yaml,
    now,
    rel,
    sha256_file,
    write_bytes,
    write_yaml,
)
from validate_outputs import validate_freeze


REVISION_2_ONLY = {
    "state_access_ordering_within_opcode_execution",
    "state_gas_accounting_changes",
    "new_invariant_on_pre_existing_tests",
    "new_test_framework_primitives",
    "unspecified_behavior_requiring_cross_client_consensus",
}
CHANGED_COMMON = {"encoding_changes_rlp_ssz", "cross_eip_interactions"}
REVISION_1_ONLY = {"engine_api_encoding_changes"}
TIERS = ["low", "medium", "high"]


def rank(values: list[float]) -> list[float]:
    ordered = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and values[ordered[end + 1]] == values[ordered[index]]:
            end += 1
        average = (index + end + 2) / 2
        for offset in range(index, end + 1):
            result[ordered[offset]] = average
        index = end + 1
    return result


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2:
        return None
    mean_left, mean_right = statistics.mean(left), statistics.mean(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - mean_left) ** 2 for a in left) * sum((b - mean_right) ** 2 for b in right)
    )
    return numerator / denominator if denominator else None


def spearman(left: list[float], right: list[float]) -> float | None:
    return pearson(rank(left), rank(right))


def kendall_tau_b(left: list[float], right: list[float]) -> float | None:
    if len(left) < 2:
        return None
    concordant = discordant = left_ties = right_ties = 0
    for first in range(len(left)):
        for second in range(first + 1, len(left)):
            dx = (left[first] > left[second]) - (left[first] < left[second])
            dy = (right[first] > right[second]) - (right[first] < right[second])
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                left_ties += 1
            elif dy == 0:
                right_ties += 1
            elif dx == dy:
                concordant += 1
            else:
                discordant += 1
    denominator = math.sqrt(
        (concordant + discordant + left_ties) * (concordant + discordant + right_ties)
    )
    return (concordant - discordant) / denominator if denominator else None


def rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def rubric_mapping(current: dict[str, Any], old: dict[str, Any]) -> list[dict[str, Any]]:
    current_by_id = {item["id"]: item for item in current["criteria"]}
    old_by_id = {item["id"]: item for item in old["criteria"]}
    mapping: list[dict[str, Any]] = []
    for criterion_id, item in old_by_id.items():
        if criterion_id in REVISION_1_ONLY:
            status = "revision_1_only"
            related = ["encoding_changes_rlp_ssz"]
        elif criterion_id in CHANGED_COMMON:
            status = "changed"
            related = [criterion_id]
        elif criterion_id in current_by_id:
            status = "exact"
            related = [criterion_id]
        else:
            status = "unmapped"
            related = []
        mapping.append(
            {
                "revision_1_id": criterion_id,
                "revision_1_label": item["label"],
                "revision_1_score": item["score"],
                "status": status,
                "revision_2_ids": related,
                "revision_2_scores": [current_by_id[target]["score"] for target in related if target in current_by_id],
            }
        )
    for criterion_id in [item["id"] for item in current["criteria"]]:
        if criterion_id in REVISION_2_ONLY:
            item = current_by_id[criterion_id]
            mapping.append(
                {
                    "revision_1_id": None,
                    "revision_1_label": None,
                    "revision_1_score": None,
                    "status": "revision_2_only",
                    "revision_2_ids": [criterion_id],
                    "revision_2_scores": [item["score"]],
                }
            )
    return mapping


def build_comparison(item: dict[str, Any]) -> dict[str, Any]:
    number = int(item["eip"]["number"])
    current_path = REPO_ROOT / item["task_05_output"]["path"]
    old_path = AUTOMATED_ROOT / f"eip-{number}.yaml"
    human_path = REPO_ROOT / item["human_record"]["path"]
    current = load_yaml(current_path)
    old = load_yaml(old_path)
    human = load_yaml(human_path)
    human_by_id = {score["id"]: score for score in human["scores"]}
    old_by_id = {criterion["id"]: criterion for criterion in old["criteria"]}
    per_anchor = []
    for criterion in old["criteria"]:
        human_score = human_by_id[criterion["id"]]
        contribution = human_score["numeric_contribution"]
        difference = criterion["score"] - contribution if contribution is not None else None
        per_anchor.append(
            {
                "id": criterion["id"],
                "label": criterion["label"],
                "human_raw_score_cell": human_score["raw_score_cell"],
                "human_parsed_terms": human_score["parsed_terms"],
                "human_normalized_contribution": contribution,
                "automated_historical_score": criterion["score"],
                "b_minus_c": difference,
                "absolute_error": abs(difference) if difference is not None else None,
            }
        )
    a_total = int(current["totals"]["primary_score"])
    b_total = int(old["totals"]["primary_score"])
    c_total = int(human["recomputed_total"])
    b_minus_c = b_total - c_total
    a_minus_b = a_total - b_total
    differing_judgments = [row["id"] for row in per_anchor if row["b_minus_c"] != 0]
    return {
        "schema_version": 1,
        "task_id": "05c-amsterdam-human-assessment-alignment-comparison",
        "fork_id": "amsterdam",
        "eip": copy.deepcopy(item["eip"]),
        "observations": {
            "A_current_rubric_automated": {
                "path": item["task_05_output"]["path"],
                "sha256": sha256_file(current_path),
                "session_id": current["provenance"]["assessor"]["session_id"],
                "rubric_revision": 2,
                "total": a_total,
                "maximum": "84 nominal across 28 rows; Cross-EIP interactions is uncapped",
                "tier": current["totals"]["complexity_tier"],
                "thresholds": {"low": "<12", "medium": ">=12 and <23", "high": ">=23"},
            },
            "B_historical_rubric_automated": {
                "path": rel(old_path),
                "sha256": sha256_file(old_path),
                "session_id": old["provenance"]["assessor_environment"]["session_id"],
                "rubric_commit": old["provenance"]["historical_rubric"]["commit"],
                "total": b_total,
                "maximum": 72,
                "tier": old["totals"]["complexity_tier"],
                "thresholds": old["totals"]["tier_thresholds"],
            },
            "C_historical_human": {
                "path": item["human_record"]["path"],
                "sha256": sha256_file(human_path),
                "event_commit": human["human_event"]["commit"],
                "rubric_commit": human["historical_rubric"]["commit"],
                "published_total": human["published_total"],
                "recomputed_total": c_total,
                "maximum": 72,
                "published_tier": human["published_tier"],
                "recomputed_tier": human["recomputed_tier"],
                "thresholds": human["historical_rubric"]["tier_thresholds"],
            },
        },
        "confounds": {
            "input_alignment": human["input_alignment"],
            "intervening_eip_commits": human["intervening_eip_commits"],
            "template_match": human["template_match"],
            "human_timing_exposure": human["human_timing_exposure"],
        },
        "clean_comparison": {
            "eligible": item["clean_comparison_eligible"],
            "failed_conditions": item["clean_comparison_failed_conditions"],
            "low_exposure_eligible": item["low_exposure_comparison_eligible"],
        },
        "totals": {
            "b_minus_c": b_minus_c,
            "absolute_b_minus_c": abs(b_minus_c),
            "a_minus_b": a_minus_b,
            "b_vs_c_exact_total_agreement": b_total == c_total,
            "b_vs_c_tier_agreement": old["totals"]["complexity_tier"] == human["recomputed_tier"],
            "cross_rubric_warning": "A and B use different row inventories, nominal maxima, and thresholds; A-minus-B is descriptive rubric sensitivity, not a like-for-like scale estimate.",
        },
        "historical_anchor_comparison": per_anchor,
        "rubric_revision_mapping": rubric_mapping(current, old),
        "notes": {
            "factual_disagreement": "Not independently adjudicated; a nonzero anchor delta alone does not establish a factual error.",
            "rubric_interpretation": [
                "The historical Engine API encoding changes row lacks a dedicated definition in the source template.",
                "Rows marked changed or revision-specific in rubric_revision_mapping are not forced into one-to-one equivalence.",
            ],
            "evaluator_judgment": differing_judgments,
            "input_drift": human["input_alignment"]["summary"],
            "parsing": human["parser_notes"],
        },
        "provenance": {
            "comparison_script": {"path": rel(Path(__file__)), "sha256": sha256_file(Path(__file__))},
            "automated_freeze": {"path": rel(FREEZE_PATH), "sha256": sha256_file(FREEZE_PATH)},
            "consumed_inputs": [
                {"path": item["task_05_output"]["path"], "sha256": sha256_file(current_path)},
                {"path": rel(old_path), "sha256": sha256_file(old_path)},
                {"path": item["human_record"]["path"], "sha256": sha256_file(human_path)},
            ],
            "generated_at": now(),
        },
    }


def metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {
            "n": 0,
            "exact_agreement_rate": None,
            "mean_absolute_error": None,
            "median_absolute_error": None,
            "signed_bias_b_minus_c": None,
            "spearman": None,
            "kendall_tau_b": None,
            "tier_agreement_rate": None,
            "tier_confusion": {human: {automated: 0 for automated in TIERS} for human in TIERS},
        }
    b_values = [record["observations"]["B_historical_rubric_automated"]["total"] for record in records]
    c_values = [record["observations"]["C_historical_human"]["recomputed_total"] for record in records]
    differences = [b - c for b, c in zip(b_values, c_values)]
    confusion = {human: {automated: 0 for automated in TIERS} for human in TIERS}
    for record in records:
        human_tier = record["observations"]["C_historical_human"]["recomputed_tier"]
        automated_tier = record["observations"]["B_historical_rubric_automated"]["tier"]
        confusion[human_tier][automated_tier] += 1
    return {
        "n": len(records),
        "exact_agreement_rate": rounded(sum(value == 0 for value in differences) / len(records)),
        "mean_absolute_error": rounded(statistics.mean(abs(value) for value in differences)),
        "median_absolute_error": rounded(statistics.median(abs(value) for value in differences)),
        "signed_bias_b_minus_c": rounded(statistics.mean(differences)),
        "spearman": rounded(spearman(b_values, c_values)),
        "kendall_tau_b": rounded(kendall_tau_b(b_values, c_values)),
        "tier_agreement_rate": rounded(
            sum(record["totals"]["b_vs_c_tier_agreement"] for record in records) / len(records)
        ),
        "tier_confusion": confusion,
    }


def per_anchor_metrics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: dict[str, list[int]] = defaultdict(list)
    labels: dict[str, str] = {}
    for record in records:
        for row in record["historical_anchor_comparison"]:
            labels[row["id"]] = row["label"]
            if row["b_minus_c"] is not None:
                values[row["id"]].append(row["b_minus_c"])
    return [
        {
            "id": criterion_id,
            "label": labels[criterion_id],
            "n": len(differences),
            "mean_signed_difference": rounded(statistics.mean(differences)) if differences else None,
            "mean_absolute_difference": rounded(statistics.mean(abs(value) for value in differences)) if differences else None,
        }
        for criterion_id, differences in values.items()
    ]


def confusion_table(confusion: dict[str, dict[str, int]]) -> str:
    lines = ["| Human \\ Automated | Low | Medium | High |", "|---|---:|---:|---:|"]
    for human in TIERS:
        lines.append(
            f"| {human.title()} | {confusion[human]['low']} | {confusion[human]['medium']} | {confusion[human]['high']} |"
        )
    return "\n".join(lines)


def format_metric(value: Any) -> str:
    return "not estimable" if value is None else str(value)


def build_summary(inventory: dict[str, Any], records: list[dict[str, Any]]) -> str:
    clean = [record for record in records if record["clean_comparison"]["eligible"]]
    confounded = [record for record in records if not record["clean_comparison"]["eligible"]]
    low_exposure = [record for record in records if record["clean_comparison"]["low_exposure_eligible"]]
    all_metrics, clean_metrics = metrics(records), metrics(clean)
    exposure_counts = Counter(
        record["confounds"]["human_timing_exposure"]["classification"] for record in records
    )
    drift_cases = [
        record
        for record in records
        if record["confounds"]["input_alignment"]["classification"] not in {"exact_blob", "no_substantive_drift"}
    ]
    revision_effects = [record["totals"]["a_minus_b"] for record in records]
    strongest = min(records, key=lambda record: record["totals"]["absolute_b_minus_c"])
    weakest = max(records, key=lambda record: record["totals"]["absolute_b_minus_c"])
    excluded = [item for item in inventory["eips"] if item["status"] == "excluded"]
    low_exposure_label = "comparison" if len(low_exposure) == 1 else "comparisons"
    low_exposure_verb = "has" if len(low_exposure) == 1 else "have"
    lines = [
        "# Amsterdam historical-checklist alignment summary",
        "",
        "This calibration study compares a newly blinded historical-checklist automated assessment (B) with the published historical human assessment (C). The existing checklist-revision-2 automated result (A) is included only for controlled rubric sensitivity on the same Task 04 input. Task 05c scores are not primary fork scores.",
        "",
        "## Population",
        "",
        f"The mechanically derived population contains {len(records)} included EIPs from {inventory['counts']['approved_task_04']} approved Amsterdam refs. {len(excluded)} were excluded: "
        + "; ".join(f"EIP-{item['eip']['number']} ({', '.join(item['exclusion_reasons'])})" for item in excluded)
        + ".",
        "",
        f"Only {len(clean)} comparisons meet the predeclared clean-input/template/total conditions; {len(confounded)} are descriptive confounded comparisons. {len(low_exposure)} clean {low_exposure_label} also {low_exposure_verb} low classified hindsight exposure.",
        "",
        "## Human–automated alignment (B versus C)",
        "",
        "| Subset | N | Exact total agreement | Mean absolute error | Median absolute error | Signed bias (B-C) | Spearman | Kendall tau-b | Tier agreement |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| All reconstructable | {all_metrics['n']} | {format_metric(all_metrics['exact_agreement_rate'])} | {format_metric(all_metrics['mean_absolute_error'])} | {format_metric(all_metrics['median_absolute_error'])} | {format_metric(all_metrics['signed_bias_b_minus_c'])} | {format_metric(all_metrics['spearman'])} | {format_metric(all_metrics['kendall_tau_b'])} | {format_metric(all_metrics['tier_agreement_rate'])} |",
        f"| Clean | {clean_metrics['n']} | {format_metric(clean_metrics['exact_agreement_rate'])} | {format_metric(clean_metrics['mean_absolute_error'])} | {format_metric(clean_metrics['median_absolute_error'])} | {format_metric(clean_metrics['signed_bias_b_minus_c'])} | {format_metric(clean_metrics['spearman'])} | {format_metric(clean_metrics['kendall_tau_b'])} | {format_metric(clean_metrics['tier_agreement_rate'])} |",
        "",
        "The clean subset has only two records; its rank correlations are arithmetic outputs and are not substantively interpretable.",
        "",
        "Clean tier confusion (rows are human, columns automated):",
        "",
        confusion_table(clean_metrics["tier_confusion"]),
        "",
        "Per-anchor differences are stored in every comparison record. Aggregate all-row per-anchor means:",
        "",
        "| Historical anchor | N | Mean signed B-C | Mean absolute difference |",
        "|---|---:|---:|---:|",
    ]
    for anchor in per_anchor_metrics(records):
        lines.append(
            f"| {anchor['label']} | {anchor['n']} | {format_metric(anchor['mean_signed_difference'])} | {format_metric(anchor['mean_absolute_difference'])} |"
        )
    lines.extend(
        [
            "",
            "## Confounds",
            "",
            f"Substantive or unknown EIP-input drift affects {len(drift_cases)} records: "
            + ", ".join(f"EIP-{record['eip']['number']}" for record in drift_cases)
            + ". These rows are excluded from the clean aggregate even though they remain in the descriptive dataset.",
            "",
            "Human timing exposure counts: " + ", ".join(f"{key}={value}" for key, value in sorted(exposure_counts.items())) + ". Exposure is reported separately and does not retroactively alter the historical record.",
            "",
            "## Rubric revision effect (A versus B)",
            "",
            f"Across {len(records)} same-input automated pairs, mean A-minus-B is {rounded(statistics.mean(revision_effects))}, median is {rounded(statistics.median(revision_effects))}, and the range is {min(revision_effects)} to {max(revision_effects)}. A uses 28 rows, revision-2 thresholds (<12, 12–22, >=23), and an uncapped Cross-EIP row; B uses 24 rows, a nominal maximum of 72, and historical thresholds (<10, 10–19, >=20). The delta is therefore descriptive sensitivity, not a common-scale causal estimate.",
            "",
            "## Qualitative examples",
            "",
            f"The smallest observed total difference is EIP-{strongest['eip']['number']} (B={strongest['observations']['B_historical_rubric_automated']['total']}, C={strongest['observations']['C_historical_human']['recomputed_total']}, absolute error={strongest['totals']['absolute_b_minus_c']}).",
            "",
            f"The largest material disagreement is EIP-{weakest['eip']['number']} (B={weakest['observations']['B_historical_rubric_automated']['total']}, C={weakest['observations']['C_historical_human']['recomputed_total']}, absolute error={weakest['totals']['absolute_b_minus_c']}); interpret it with its recorded input-alignment, template-match, and timing-exposure classifications rather than as a pure evaluator error.",
            "",
            "## Limitations",
            "",
            "The Amsterdam sample is small, and the clean subset is smaller still, so rank statistics and percentages are unstable descriptions rather than decisive estimates. Amsterdam evidence contributed to later checklist work, making the fork in-sample for revision 2 even though the B runs were blinded. Human reviews sometimes used implementation or test knowledge and often saw later EIP states. Model latent knowledge cannot be removed; package-grounded evidence and isolation reduce observable hindsight channels but cannot erase learned background knowledge. No rubric weights were optimized, no p-values are used, and no causal claim is made.",
            "",
        ]
    )
    return "\n".join(lines)


def dataset_manifest(inventory: dict[str, Any]) -> dict[str, Any]:
    task_files: list[Path] = []
    for root in (
        TASK_ROOT / "inputs",
        TASK_ROOT / "outputs",
        TASK_ROOT / "prompts",
        TASK_ROOT / "scripts",
        TASK_ROOT / "templates",
    ):
        task_files.extend(path for path in root.rglob("*") if path.is_file())
    task_files.extend([TASK_ROOT / "TASK.md", TASK_ROOT / "pyproject.toml"])
    task_files = [path for path in task_files if path != DATASET_MANIFEST_PATH and "__pycache__" not in path.parts]
    external_files: list[Path] = []
    for item in inventory["eips"]:
        external_files.append(REPO_ROOT / item["task_04_ref"]["path"])
        manifest = REPO_ROOT / item["task_05_package_manifest"]["path"]
        output = REPO_ROOT / item["task_05_output"]["path"]
        if manifest.is_file():
            external_files.append(manifest)
        if output.is_file():
            external_files.append(output)
    entries = [
        {"path": rel(path), "sha256": sha256_file(path)}
        for path in sorted(set(task_files + external_files))
    ]
    return {
        "schema_version": 1,
        "task_id": "05c-amsterdam-human-assessment-alignment-dataset",
        "generated_at": now(),
        "manifest_scope": "All task-owned inputs, packages, automated results, human records, comparisons, prompts, contract, rubrics, scripts, templates, and frozen Task 04/05 joins required to reproduce the study. This self-describing manifest excludes its own hash.",
        "source_commits": {
            name: source["head"] for name, source in inventory["source_repositories"].items()
        },
        "files": entries,
    }


def main() -> int:
    validate_freeze()  # mandatory reveal gate
    inventory = load_yaml(INVENTORY_PATH)
    included = [item for item in inventory["eips"] if item["status"] == "included"]
    records: list[dict[str, Any]] = []
    for item in included:
        number = int(item["eip"]["number"])
        comparison = build_comparison(item)
        path = COMPARISON_ROOT / f"eip-{number}.yaml"
        write_yaml(path, comparison)
        records.append(comparison)
        print(
            f"comparison EIP-{number}: B-C={comparison['totals']['b_minus_c']:+d} "
            f"A-B={comparison['totals']['a_minus_b']:+d} "
            f"clean={comparison['clean_comparison']['eligible']}"
        )
    write_bytes(SUMMARY_PATH, build_summary(inventory, records).encode())
    write_yaml(DATASET_MANIFEST_PATH, dataset_manifest(inventory))
    print(f"wrote {len(records)} comparisons, alignment summary, and dataset manifest")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StudyError as error:
        raise SystemExit(f"comparison error: {error}") from error
