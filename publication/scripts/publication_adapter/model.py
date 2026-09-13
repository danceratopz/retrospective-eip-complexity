"""Projection of research records into sanitized assessment objects.

An *assessment* is one scored (or attempted) application of one rubric revision to one EIP in one fork
context by one source (``llm`` or ``human``). Every assessment shares the same shape so the site renders
all of them with one component set.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    SOURCE_HUMAN,
    SOURCE_LLM,
    STATUS_AVAILABLE_IN_OPEN_PR,
    STATUS_COMPLETE,
    STATUS_INCOMPLETE,
    STATUS_IN_PROGRESS,
    BuildError,
    assessment_id,
    github_current_revision,
    github_revision_history,
    relative,
    source,
)
from .rubric import RUBRIC_ORDER, tier_for


def _evidence(items: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    return [
        {"source": item["source"], "locator": item["locator"], "summary": item["summary"]}
        for item in (items or [])
    ]


def _revision_provenance(record: dict[str, Any], *, note: str | None = None) -> dict[str, Any]:
    projected = {
        "repository": record["repository"],
        "commit": record["commit"],
        "path": record["path"],
        "committed_at": record.get("committed_at"),
        "git_blob_sha": record.get("git_blob_sha"),
        "content_sha256": record.get("content_sha256"),
        "immutable_url": record["immutable_url"],
        "information_cutoff_at": record.get("information_cutoff_at"),
        "current_revision_url": github_current_revision(record["path"]),
        "revision_history_url": github_revision_history(record["path"]),
    }
    if note:
        projected["note"] = note
    return projected


def _rubric_provenance(record: dict[str, Any], revision: int) -> dict[str, Any]:
    return {
        "revision": revision,
        "repository": record["repository"],
        "commit": record["commit"],
        "path": record["path"],
        "immutable_url": record["immutable_url"],
    }


def validate_scores(criteria: list[dict[str, Any]], score: int, tier: str, revision: int, context: str) -> None:
    ids = [item["id"] for item in criteria]
    if ids != RUBRIC_ORDER[revision]:
        raise BuildError(f"{context}: criterion inventory does not match rubric revision {revision}")
    total = sum(item["score"] for item in criteria)
    if total != score:
        raise BuildError(f"{context}: criterion scores sum to {total}, not the recorded total {score}")
    if tier_for(score, revision) != tier:
        raise BuildError(f"{context}: tier {tier!r} does not match score {score} under revision {revision}")


def llm_assessment(
    record: dict[str, Any],
    *,
    path: Path,
    fork: str,
    mode: str,
    revision: int,
    role: str,
    summary_key: str,
    eip_key: str,
    rubric_key: str,
    assessor_key: str,
) -> dict[str, Any]:
    """Project a Task 05, Task 05c automated, or Task 08 assessment record."""
    eip = record["eip"]["number"]
    context = f"{fork} EIP-{eip} {SOURCE_LLM} r{revision}"
    totals = record["totals"]
    score = totals["primary_score"]
    tier = totals["complexity_tier"]
    validate_scores(record["criteria"], score, tier, revision, context)
    under = record["under_specification"]
    affected = set(under.get("affected_criteria") or [])
    unknown = affected - set(RUBRIC_ORDER[revision])
    if unknown:
        raise BuildError(f"{context}: under-specification names unknown criteria {sorted(unknown)}")
    criteria = []
    for item in record["criteria"]:
        projected = {
            "id": item["id"],
            "score": item["score"],
            "rationale": item["rationale"],
            "evidence": _evidence(item.get("evidence")),
            "confidence": item.get("confidence"),
            "uncertainty_note": item.get("uncertainty_note"),
            "exceptional_score_justification": item.get("exceptional_score_justification"),
            "under_specified": item["id"] in affected,
        }
        if "interacting_eips" in item:
            projected["interacting_eips"] = list(item["interacting_eips"] or [])
        if "unidentified_interactions" in item:
            projected["unidentified_interactions"] = list(item["unidentified_interactions"] or [])
        criteria.append(projected)
    provenance = record["provenance"]
    assessor = provenance[assessor_key]
    plausible = under.get("plausible_total_range") or {}
    return {
        "id": assessment_id(fork, eip, SOURCE_LLM, revision),
        "eip": eip,
        "title": record["eip"]["title"],
        "fork": fork,
        "mode": mode,
        "source": SOURCE_LLM,
        "rubric_revision": revision,
        "role": role,
        "status": STATUS_COMPLETE,
        "scored": True,
        "score": score,
        "tier": tier,
        "confidence": record["overall_confidence"],
        "summary": record["assessment"][summary_key],
        "criteria": criteria,
        "under_specification": {
            "present": bool(under["present"]),
            "summary": under.get("summary"),
            "affected_criteria": sorted(affected, key=RUBRIC_ORDER[revision].index),
            "plausible_total_range": (
                {"minimum": plausible["minimum"], "maximum": plausible["maximum"]} if plausible else None
            ),
            "plausible_tiers": list(under.get("plausible_tiers") or []),
            "unresolved_questions": list(under.get("unresolved_questions") or []),
        },
        "notable_ambiguities": list(record.get("notable_ambiguities") or []),
        "provenance": {
            "assessed_revision": _revision_provenance(provenance[eip_key]),
            "rubric": _rubric_provenance(provenance[rubric_key], revision),
            "assessor": {
                "kind": SOURCE_LLM,
                "model": assessor["model"],
                "reasoning_effort": assessor["reasoning_effort"],
                "isolation_method": assessor.get("isolation_method"),
            },
            "source_record": {"kind": "research_record", "path": relative(path), "sha256": source(path)["sha256"]},
            "supporting_documents": [
                item for item in (provenance.get("sources_consulted") or []) if item not in {"eip.md", "rubric.md"}
            ],
        },
    }


def _human_criteria(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "score": item["numeric_contribution"],
            "raw_score_cell": item["raw_score_cell"],
            "rationale": item["rationale"] or None,
            "evidence": [],
            "confidence": None,
            "uncertainty_note": None,
            "exceptional_score_justification": None,
            "blank_interpretation": item.get("blank_interpretation"),
            "under_specified": False,
        }
        for item in scores
    ]


def human_assessment_from_05c(record: dict[str, Any], *, path: Path, fork: str) -> dict[str, Any]:
    """Project one Task 05c reconstructed historical human checklist (revision 1)."""
    eip = record["eip"]["number"]
    revision = 1
    context = f"{fork} EIP-{eip} {SOURCE_HUMAN} r{revision}"
    scored = bool(record["numeric_total_unambiguous"])
    criteria = _human_criteria(record["scores"])
    score = record["recomputed_total"] if scored else None
    tier = record["recomputed_tier"] if scored else None
    if scored:
        validate_scores(criteria, score, tier, revision, context)
    event = record["human_event"]
    rubric = record["historical_rubric"]
    human_time_eip = record.get("human_time_eip")
    return {
        "id": assessment_id(fork, eip, SOURCE_HUMAN, revision),
        "eip": eip,
        "title": record["eip"]["title"],
        "fork": fork,
        "mode": "retrospective",
        "source": SOURCE_HUMAN,
        "rubric_revision": revision,
        "role": "published_checklist",
        "status": STATUS_COMPLETE if scored else STATUS_INCOMPLETE,
        "scored": scored,
        "score": score,
        "tier": tier,
        "confidence": None,
        "summary": None,
        "criteria": criteria,
        "under_specification": None,
        "notable_ambiguities": [],
        "checklist": {
            "published_total": record["published_total"],
            "published_tier": record["published_tier"],
            "recomputed_total": record["recomputed_total"],
            "recomputed_tier": record["recomputed_tier"],
            "parser_notes": list(record.get("parser_notes") or []),
            "input_alignment": (record.get("input_alignment") or {}).get("classification"),
            "timing_exposure": (record.get("human_timing_exposure") or {}).get("classification"),
        },
        "provenance": {
            "assessed_revision": (
                _revision_provenance(
                    human_time_eip,
                    note="EIP master revision at the time of the human checklist commit; the checklist itself does not pin an EIP revision.",
                )
                if human_time_eip
                else None
            ),
            "rubric": _rubric_provenance(rubric, revision),
            "assessor": {"kind": SOURCE_HUMAN, "organization": "STEEL team", "publication": "ethspecs/pm complexity_assessments"},
            "source_record": {
                "kind": "merged",
                "repository": event["repository"],
                "commit": event["commit"],
                "committed_at": event["committed_at"],
                "path": event["path"],
                "git_blob_sha": event["git_blob_sha"],
                "content_sha256": event["content_sha256"],
                "immutable_url": event["immutable_url"],
            },
            "research_record": {"path": relative(path), "sha256": source(path)["sha256"]},
            "supporting_documents": [],
        },
    }


AVAILABILITY_STATUS = {
    "merged": STATUS_COMPLETE,
    "open_pull_request": STATUS_AVAILABLE_IN_OPEN_PR,
    "open_draft_pull_request": STATUS_IN_PROGRESS,
}


def human_assessment_from_task09(
    candidate: dict[str, Any],
    *,
    eip: int,
    title: str,
    status: str,
    path: Path,
    rubric_sources: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Project one Task 09 checklist candidate for a Hegotá EIP."""
    fork = "hegota"
    revision = candidate["rubric_revision"]
    context = f"{fork} EIP-{eip} {SOURCE_HUMAN} r{revision}"
    scored = candidate["parse_state"] == "complete"
    criteria = _human_criteria(candidate["scores"])
    score = candidate["recomputed_total"] if scored else None
    tier = candidate["recomputed_tier"] if scored else None
    if scored:
        validate_scores(criteria, score, tier, revision, context)
    origin = candidate["source"]
    if origin["kind"] == "default_branch":
        source_record = {
            "kind": "merged",
            "repository": origin["repository"],
            "branch": origin["branch"],
            "commit": origin["commit"],
            "committed_at": origin["last_committed_at"],
            "path": origin["path"],
            "git_blob_sha": origin["git_blob_sha"],
            "content_sha256": origin["content_sha256"],
            "immutable_url": origin["immutable_url"],
        }
    else:
        source_record = {
            "kind": "open_draft_pull_request" if origin["draft"] else "open_pull_request",
            "repository": origin["repository"],
            "pull_request": {
                "number": origin["pull_request"],
                "title": origin["pull_request_title"],
                "url": origin["pull_request_url"],
                "draft": origin["draft"],
                "updated_at": origin["updated_at"],
            },
            "commit": origin["head_sha"],
            "path": origin["path"],
            "git_blob_sha": origin["git_blob_sha"],
            "content_sha256": origin["content_sha256"],
            "immutable_url": origin["immutable_url"],
        }
    return {
        "id": assessment_id(fork, eip, SOURCE_HUMAN, revision),
        "eip": eip,
        "title": title,
        "fork": fork,
        "mode": "prospective",
        "source": SOURCE_HUMAN,
        "rubric_revision": revision,
        "role": "published_checklist",
        "status": status,
        "scored": scored,
        "score": score,
        "tier": tier,
        "confidence": None,
        "summary": None,
        "criteria": criteria,
        "under_specification": None,
        "notable_ambiguities": [],
        "checklist": {
            "published_total": candidate["published_total"],
            "published_tier": candidate["published_tier"],
            "recomputed_total": candidate["recomputed_total"],
            "recomputed_tier": candidate["recomputed_tier"],
            "parser_notes": list(candidate.get("parser_notes") or []),
            "unresolved_blank_rows": list(candidate.get("unresolved_blank_rows") or []),
            "invalid_score_rows": list(candidate.get("invalid_score_rows") or []),
            "missing_rows": list(candidate.get("missing_rows") or []),
        },
        "provenance": {
            "assessed_revision": None,
            "rubric": {"revision": revision, **rubric_sources[revision]},
            "assessor": {"kind": SOURCE_HUMAN, "organization": "STEEL team", "publication": "ethspecs/pm complexity_assessments"},
            "source_record": source_record,
            "research_record": {"path": relative(path), "sha256": source(path)["sha256"]},
            "supporting_documents": [],
        },
    }
