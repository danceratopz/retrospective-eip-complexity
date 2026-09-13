"""Same-rubric Human-versus-LLM comparisons."""

from __future__ import annotations

from typing import Any

import re
import statistics
from pathlib import Path

from .common import SOURCE_HUMAN, SOURCE_LLM, TASK05C, BuildError, source
from .rubric import RUBRIC_ORDER


def agreement_class(delta: int) -> str:
    magnitude = abs(delta)
    if magnitude == 0:
        return "exact"
    if magnitude == 1:
        return "minor"
    return "major"


def build_comparisons(
    assessments: dict[str, dict[str, Any]], task05c: dict[int, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Pair every scored human assessment with the scored LLM assessment of the same fork, EIP, and rubric."""
    by_key: dict[tuple[str, int, int], dict[str, dict[str, Any]]] = {}
    for assessment in assessments.values():
        if not assessment["scored"]:
            continue
        key = (assessment["fork"], assessment["eip"], assessment["rubric_revision"])
        by_key.setdefault(key, {})[assessment["source"]] = assessment
    comparisons: dict[str, dict[str, Any]] = {}
    for (fork, eip, revision), pair in sorted(by_key.items()):
        if SOURCE_HUMAN not in pair or SOURCE_LLM not in pair:
            continue
        human = pair[SOURCE_HUMAN]
        llm = pair[SOURCE_LLM]
        human_scores = {item["id"]: item["score"] for item in human["criteria"]}
        llm_scores = {item["id"]: item["score"] for item in llm["criteria"]}
        rows = []
        counts = {"exact": 0, "minor": 0, "major": 0}
        for criterion_id in RUBRIC_ORDER[revision]:
            delta = llm_scores[criterion_id] - human_scores[criterion_id]
            klass = agreement_class(delta)
            counts[klass] += 1
            rows.append(
                {
                    "id": criterion_id,
                    "human": human_scores[criterion_id],
                    "llm": llm_scores[criterion_id],
                    "delta": delta,
                    "agreement": klass,
                }
            )
        comparison = {
            "id": f"{fork}:{eip}:r{revision}",
            "eip": eip,
            "fork": fork,
            "rubric_revision": revision,
            "human_assessment_id": human["id"],
            "llm_assessment_id": llm["id"],
            "human_total": human["score"],
            "llm_total": llm["score"],
            "delta": llm["score"] - human["score"],
            "absolute_delta": abs(llm["score"] - human["score"]),
            "human_tier": human["tier"],
            "llm_tier": llm["tier"],
            "tier_agreement": human["tier"] == llm["tier"],
            "rows": rows,
            "agreement_counts": counts,
            "largest_disagreements": [
                row["id"]
                for row in sorted(rows, key=lambda row: (-abs(row["delta"]), RUBRIC_ORDER[revision].index(row["id"])))
                if row["delta"] != 0
            ][:5],
            "confounds": None,
        }
        if fork == "amsterdam" and eip in task05c:
            record = task05c[eip]
            expected = {row["id"]: row["b_minus_c"] for row in record["historical_anchor_comparison"]}
            observed = {row["id"]: row["delta"] for row in rows}
            if observed != expected or record["totals"]["b_minus_c"] != comparison["delta"]:
                raise BuildError(f"Amsterdam EIP-{eip} comparison deltas differ from the Task 05c record")
            confounds = record["confounds"]
            comparison["confounds"] = {
                "clean_comparison": bool(record["clean_comparison"]["eligible"]),
                "failed_conditions": list(record["clean_comparison"].get("failed_conditions") or []),
                "input_alignment": confounds["input_alignment"]["classification"],
                "input_alignment_summary": confounds["input_alignment"].get("summary"),
                "template_match": confounds["template_match"]["classification"],
                "human_timing_exposure": confounds["human_timing_exposure"]["classification"],
                "human_timing_exposure_rationale": confounds["human_timing_exposure"].get("rationale"),
                "primary_llm_total": record["observations"]["A_current_rubric_automated"]["total"],
                "cross_rubric_warning": record["totals"].get("cross_rubric_warning"),
            }
        comparisons[comparison["id"]] = comparison
    return comparisons


ALIGNMENT_SUMMARY = TASK05C / "outputs/alignment-summary.md"
REVISION_1_LABELS = {
    "EVM Gas rule changes": "evm_gas_rule_changes",
    "Blob gas accounting changes": "blob_gas_accounting_changes",
    "New EVM gas refund": "new_evm_gas_refund",
    "Patterns affecting pre-existing tests": "patterns_affecting_pre_existing_tests",
    "Transition-tool interface changes": "transition_tool_interface_changes",
    "Cryptography-related testing": "cryptography",
    "Edge/boundary conditions": "edge_boundary_conditions",
    "Block syncing changes": "block_syncing_changes",
    "Engine API changes": "engine_api_changes",
    "Engine API encoding changes": "engine_api_encoding_changes",
    "Added system contracts": "added_system_contracts",
    "Modified system contracts": "modified_system_contracts",
    "Added opcodes": "added_opcodes",
    "Modified opcodes": "modified_opcodes",
    "Added precompiles": "added_precompiles",
    "Modified precompiles": "modified_precompiles",
    "Encoding changes (RLP/SSZ)": "encoding_changes_rlp_ssz",
    "New transaction types": "new_transaction_types",
    "New or modified transaction validity mechanisms": "new_or_modified_transaction_validity_mechanisms",
    "New block / header fields": "new_block_header_fields",
    "New fork activation mechanism": "new_fork_activation_mechanism",
    "Performance risks": "performance_risks",
    "Security risks": "security_risks",
    "Cross-EIP interactions": "cross_eip_interactions",
}


def _published_criterion_means(path: Path) -> dict[str, tuple[float, float]]:
    """Read the per-anchor mean signed and absolute differences from the Task 05c summary."""
    means: dict[str, tuple[float, float]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\| (.+?) \| 12 \| (-?[0-9.]+) \| (-?[0-9.]+) \|$", line)
        if match and match.group(1) in REVISION_1_LABELS:
            means[REVISION_1_LABELS[match.group(1)]] = (float(match.group(2)), float(match.group(3)))
    if len(means) != 24:
        raise BuildError("Task 05c alignment summary does not list all 24 historical anchors")
    return means


def amsterdam_alignment(
    comparisons: dict[str, dict[str, Any]], assessments: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Aggregate the Amsterdam same-rubric comparisons and cross-check them against the Task 05c summary."""
    pairs = sorted(
        (item for item in comparisons.values() if item["fork"] == "amsterdam" and item["rubric_revision"] == 1),
        key=lambda item: (-item["human_total"], item["eip"]),
    )
    if len(pairs) != 12:
        raise BuildError("Amsterdam alignment requires twelve revision-1 comparisons")
    rows = []
    for comparison in pairs:
        human = assessments[comparison["human_assessment_id"]]
        llm = assessments[comparison["llm_assessment_id"]]
        primary = assessments.get(f"amsterdam:{comparison['eip']}:llm:r2")
        confounds = comparison["confounds"] or {}
        rows.append(
            {
                "clean": bool(confounds.get("clean_comparison")),
                "comparison_id": comparison["id"],
                "delta": comparison["delta"],
                "eip": comparison["eip"],
                "human_assessment_id": human["id"],
                "human_tier": comparison["human_tier"],
                "human_timing_exposure": confounds.get("human_timing_exposure"),
                "human_total": comparison["human_total"],
                "input_alignment": confounds.get("input_alignment"),
                "llm_assessment_id": llm["id"],
                "llm_tier": comparison["llm_tier"],
                "llm_total": comparison["llm_total"],
                "primary_llm_assessment_id": primary["id"] if primary else None,
                "primary_llm_total": primary["score"] if primary else None,
                "tier_agreement": comparison["tier_agreement"],
                "title": human["title"],
            }
        )
    deltas = [row["delta"] for row in rows]
    summary = {
        "clean_count": sum(1 for row in rows if row["clean"]),
        "comparison_count": len(rows),
        "equal_total_count": sum(1 for value in deltas if value == 0),
        "human_higher_count": sum(1 for value in deltas if value < 0),
        "llm_higher_count": sum(1 for value in deltas if value > 0),
        "mean_absolute_delta": round(statistics.mean(abs(value) for value in deltas), 4),
        "mean_signed_delta": round(statistics.mean(deltas), 4),
        "median_absolute_delta": statistics.median(abs(value) for value in deltas),
        "tier_agreement_count": sum(1 for row in rows if row["tier_agreement"]),
    }
    criteria = []
    published = _published_criterion_means(ALIGNMENT_SUMMARY)
    for criterion_id in RUBRIC_ORDER[1]:
        cells = [next(cell for cell in comparison["rows"] if cell["id"] == criterion_id) for comparison in pairs]
        mean_delta = round(statistics.mean(cell["delta"] for cell in cells), 4)
        mean_absolute = round(statistics.mean(abs(cell["delta"]) for cell in cells), 4)
        expected_signed, expected_absolute = published[criterion_id]
        if abs(mean_delta - expected_signed) > 0.0001 or abs(mean_absolute - expected_absolute) > 0.0001:
            raise BuildError(f"Amsterdam per-criterion means for {criterion_id} differ from the Task 05c summary")
        criteria.append(
            {
                "exact_count": sum(1 for cell in cells if cell["delta"] == 0),
                "human_higher_count": sum(1 for cell in cells if cell["delta"] < 0),
                "id": criterion_id,
                "llm_higher_count": sum(1 for cell in cells if cell["delta"] > 0),
                "mean_absolute_delta": mean_absolute,
                "mean_delta": mean_delta,
                "nonzero_count": sum(1 for cell in cells if cell["human"] or cell["llm"]),
            }
        )
    if summary["mean_absolute_delta"] != 5.3333 or summary["mean_signed_delta"] != 2.8333 or summary["tier_agreement_count"] != 2:
        raise BuildError("Amsterdam alignment summary statistics differ from the Task 05c summary")
    return {
        "criteria": criteria,
        "fork": "amsterdam",
        "rows": rows,
        "rubric_revision": 1,
        "summary": summary,
    }, [source(ALIGNMENT_SUMMARY)]
