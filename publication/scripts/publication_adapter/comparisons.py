"""Human-versus-LLM comparisons against the primary Opus 5.5 · v3 assessment."""

from __future__ import annotations

from typing import Any

import statistics

from .common import SOURCE_HUMAN, SOURCE_LLM, BuildError
from .rubric import REGISTRY_ORDER, RUBRIC_ORDER


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
    """Pair each published human checklist with the primary LLM assessment (Opus 5.5 · v3) of the same occurrence.

    The two may apply different checklist revisions. Revision 3 rephrases the criteria of revisions 1 and 2
    more precisely, so per-criterion differences are computed for criteria present in both revisions;
    a criterion that exists in only one revision is shown without a difference.
    """
    pairs: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for assessment in assessments.values():
        if not assessment["scored"]:
            continue
        if assessment["source"] == SOURCE_HUMAN or assessment.get("role") == "primary":
            pairs.setdefault((assessment["fork"], assessment["eip"]), {})[assessment["source"]] = assessment
    comparisons: dict[str, dict[str, Any]] = {}
    for (fork, eip), pair in sorted(pairs.items()):
        if SOURCE_HUMAN not in pair or SOURCE_LLM not in pair:
            continue
        human = pair[SOURCE_HUMAN]
        llm = pair[SOURCE_LLM]
        human_revision, llm_revision = human["rubric_revision"], llm["rubric_revision"]
        human_scores = {item["id"]: item["score"] for item in human["criteria"]}
        llm_scores = {item["id"]: item["score"] for item in llm["criteria"]}
        criterion_ids = [item for item in REGISTRY_ORDER if item in human_scores or item in llm_scores]
        rows = []
        counts = {"exact": 0, "minor": 0, "major": 0}
        for criterion_id in criterion_ids:
            shared = criterion_id in human_scores and criterion_id in llm_scores
            delta = llm_scores[criterion_id] - human_scores[criterion_id] if shared else None
            klass = agreement_class(delta) if shared else None
            if klass:
                counts[klass] += 1
            rows.append(
                {
                    "id": criterion_id,
                    "human": human_scores.get(criterion_id),
                    "llm": llm_scores.get(criterion_id),
                    "delta": delta,
                    "agreement": klass,
                    "shared": shared,
                }
            )
        comparison = {
            "id": f"{fork}:{eip}:human-r{human_revision}:llm-r{llm_revision}",
            "eip": eip,
            "fork": fork,
            "rubric_revision": llm_revision,
            "human_rubric_revision": human_revision,
            "llm_rubric_revision": llm_revision,
            "same_revision": human_revision == llm_revision,
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
                for row in sorted(
                    (row for row in rows if row["shared"]),
                    key=lambda row: (-abs(row["delta"]), REGISTRY_ORDER.index(row["id"])),
                )
                if row["delta"] != 0
            ][:5],
            "confounds": None,
        }
        if fork == "amsterdam" and eip in task05c:
            # Task 05c's input and timing findings concern the human checklist against the historical EIP revision,
            # which Task 10 assesses unchanged, so they still apply; the template now differs by construction.
            confounds = task05c[eip]["confounds"]
            comparison["confounds"] = {
                "clean_comparison": False,
                "failed_conditions": ["checklist_revision_differs"],
                "input_alignment": confounds["input_alignment"]["classification"],
                "input_alignment_summary": confounds["input_alignment"].get("summary"),
                "template_match": "different_revision",
                "human_timing_exposure": confounds["human_timing_exposure"]["classification"],
                "human_timing_exposure_rationale": confounds["human_timing_exposure"].get("rationale"),
            }
        comparisons[comparison["id"]] = comparison
    return comparisons


def amsterdam_alignment(
    comparisons: dict[str, dict[str, Any]], assessments: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Aggregate the twelve Amsterdam comparisons of revision-1 human checklists with Opus 5.5 · v3."""
    pairs = sorted(
        (item for item in comparisons.values() if item["fork"] == "amsterdam"),
        key=lambda item: (-item["human_total"], item["eip"]),
    )
    if len(pairs) != 12:
        raise BuildError("Amsterdam alignment requires twelve comparisons")
    rows = []
    for comparison in pairs:
        human = assessments[comparison["human_assessment_id"]]
        confounds = comparison["confounds"] or {}
        rows.append(
            {
                "comparison_id": comparison["id"],
                "delta": comparison["delta"],
                "eip": comparison["eip"],
                "human_assessment_id": human["id"],
                "human_rubric_revision": comparison["human_rubric_revision"],
                "human_tier": comparison["human_tier"],
                "human_timing_exposure": confounds.get("human_timing_exposure"),
                "human_total": comparison["human_total"],
                "input_alignment": confounds.get("input_alignment"),
                "llm_assessment_id": comparison["llm_assessment_id"],
                "llm_rubric_revision": comparison["llm_rubric_revision"],
                "llm_tier": comparison["llm_tier"],
                "llm_total": comparison["llm_total"],
                "tier_agreement": comparison["tier_agreement"],
                "title": human["title"],
            }
        )
    deltas = [row["delta"] for row in rows]
    summary = {
        "comparison_count": len(rows),
        "equal_total_count": sum(1 for value in deltas if value == 0),
        "human_higher_count": sum(1 for value in deltas if value < 0),
        "llm_higher_count": sum(1 for value in deltas if value > 0),
        "mean_absolute_delta": round(statistics.mean(abs(value) for value in deltas), 4),
        "mean_signed_delta": round(statistics.mean(deltas), 4),
        "median_absolute_delta": statistics.median(abs(value) for value in deltas),
        "tier_agreement_count": sum(1 for row in rows if row["tier_agreement"]),
    }
    shared = [item for item in RUBRIC_ORDER[1] if item in RUBRIC_ORDER[3]]
    criteria = []
    for criterion_id in shared:
        cells = [next(cell for cell in comparison["rows"] if cell["id"] == criterion_id) for comparison in pairs]
        criteria.append(
            {
                "exact_count": sum(1 for cell in cells if cell["delta"] == 0),
                "human_higher_count": sum(1 for cell in cells if cell["delta"] < 0),
                "id": criterion_id,
                "llm_higher_count": sum(1 for cell in cells if cell["delta"] > 0),
                "mean_absolute_delta": round(statistics.mean(abs(cell["delta"]) for cell in cells), 4),
                "mean_delta": round(statistics.mean(cell["delta"] for cell in cells), 4),
                "nonzero_count": sum(1 for cell in cells if cell["human"] or cell["llm"]),
            }
        )
    return {
        "criteria": criteria,
        "fork": "amsterdam",
        "human_rubric_revision": 1,
        "llm_rubric_revision": 3,
        "rows": rows,
        "rubric_revision": 3,
        "shared_criteria": len(shared),
        "summary": summary,
    }, []
