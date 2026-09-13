"""Same-rubric Human-versus-LLM comparisons."""

from __future__ import annotations

from typing import Any

from .common import SOURCE_HUMAN, SOURCE_LLM, BuildError
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
