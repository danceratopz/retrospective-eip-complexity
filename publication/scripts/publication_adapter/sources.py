"""Loaders for the frozen research inputs the adapter is allowed to read."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    FORK_NAMES,
    PROSPECTIVE_FORK,
    RETROSPECTIVE_FORKS,
    SOURCE_HUMAN,
    STATUS_NOT_APPLICABLE,
    STATUS_NOT_AVAILABLE,
    TASK04B_CUTOFFS,
    TASK05_OUTPUTS,
    TASK05C,
    TASK08_EXTENSION,
    TASK08_OUTPUTS,
    TASK09,
    BuildError,
    load_yaml,
    occurrence_id,
    source,
)
from .model import human_assessment_from_05c, human_assessment_from_task09, llm_assessment


HEGOTA_GATE = {
    "snapshot": "hegota-candidates-2026-08-26-ac450a4",
    "population": 46,
    "scored": 39,
    "not_applicable": 7,
    "total": 856,
}


def _base_occurrence(*, fork: str, eip: int, title: str, layers: list[str], mode: str) -> dict[str, Any]:
    return {
        "id": occurrence_id(fork, eip),
        "eip": eip,
        "title": title,
        "fork": fork,
        "fork_name": FORK_NAMES[fork],
        "mode": mode,
        "layers": list(layers),
        "snapshot_status": None,
        "scope_timing": None,
        "llm": None,
        "human": None,
        "assessment_ids": [],
        "comparison_ids": [],
    }


def _llm_summary(assessment: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": assessment["status"],
        "assessment_id": assessment["id"],
        "score": assessment["score"],
        "tier": assessment["tier"],
        "confidence": assessment["confidence"],
        "under_specified": assessment["under_specification"]["present"],
        "information_cutoff_at": assessment["provenance"]["assessed_revision"]["information_cutoff_at"],
        "assessed_revision_at": assessment["provenance"]["assessed_revision"]["committed_at"],
    }


def load_retrospective() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    """Return (occurrences, llm assessments, sources) for the five retrospective forks."""
    occurrences: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    for fork in RETROSPECTIVE_FORKS:
        cutoff_path = TASK04B_CUTOFFS / f"{fork}.yaml"
        cutoff = load_yaml(cutoff_path)
        entries = cutoff["eips"]
        if any(entry["cohort"] not in {"forecastable_at_cutoff", "late_scope"} for entry in entries):
            raise BuildError(f"Task 04b contains an unknown scope classification for {fork}")
        scope_by_eip = {
            entry["number"]: "included_at_cutoff" if entry["cohort"] == "forecastable_at_cutoff" else "added_after_cutoff"
            for entry in entries
        }
        if len(scope_by_eip) != len(entries):
            raise BuildError(f"Task 04b contains duplicate EIPs for {fork}")
        paths = sorted((TASK05_OUTPUTS / fork).glob("eip-*.yaml"))
        if {int(path.stem.removeprefix("eip-")) for path in paths} != set(scope_by_eip):
            raise BuildError(f"Task 04b scope does not match Task 05 assessments for {fork}")
        sources.append(source(cutoff_path))
        for path in paths:
            record = load_yaml(path)
            assessment = llm_assessment(
                record,
                path=path,
                fork=fork,
                mode="retrospective",
                revision=2,
                role="primary",
                summary_key="historical_scope_summary",
                eip_key="historical_eip",
                rubric_key="rubric_source",
                assessor_key="assessor",
            )
            assessments.append(assessment)
            sources.append(source(path))
            occurrence = _base_occurrence(
                fork=fork,
                eip=assessment["eip"],
                title=assessment["title"],
                layers=record["eip"]["layers"],
                mode="retrospective",
            )
            occurrence["scope_timing"] = scope_by_eip[assessment["eip"]]
            occurrence["llm"] = _llm_summary(assessment)
            occurrence["assessment_ids"].append(assessment["id"])
            occurrences.append(occurrence)
    return occurrences, assessments, sources


def load_prospective() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    """Return (occurrences, llm assessments, public summary, sources) for the Hegotá snapshot."""
    summary_path = TASK08_OUTPUTS / "summary-all-candidates.yaml"
    validation_path = TASK08_OUTPUTS / "validation-report.yaml"
    manifest_path = TASK08_OUTPUTS / "assessment-manifest.yaml"
    extension_validation_path = TASK08_EXTENSION / "validation-report.yaml"
    extension_manifest_path = TASK08_EXTENSION / "assessment-manifest.yaml"
    summary = load_yaml(summary_path)
    validation = load_yaml(validation_path)
    manifest = load_yaml(manifest_path)
    extension_validation = load_yaml(extension_validation_path)
    extension_manifest = load_yaml(extension_manifest_path)
    observed = {
        "snapshot": summary["snapshot"]["snapshot_id"],
        "population": summary["population"]["meta_eip_listed_entries"],
        "scored": summary["population"]["scored_el_rubric"],
        "not_applicable": summary["population"]["not_applicable_total"],
        "total": summary["el_rubric_totals"]["all_candidates"]["score_sum"],
    }
    if observed != HEGOTA_GATE:
        raise BuildError(f"Task 08 publication gate mismatch: {observed!r}")
    if (
        validation.get("result") != "pass"
        or manifest.get("assessment_count") != 37
        or extension_validation.get("result") != "pass"
        or extension_manifest.get("assessment_count") != 2
    ):
        raise BuildError("Task 08 validation or assessment freeze is not complete")
    sources = [
        source(summary_path),
        source(validation_path),
        source(manifest_path),
        source(extension_validation_path),
        source(extension_manifest_path),
    ]
    occurrences: list[dict[str, Any]] = []
    assessments: list[dict[str, Any]] = []
    for row in summary["scored_eips"]:
        root = TASK08_OUTPUTS / "assessments/hegota-pfi-2026-08-26" if row["snapshot_status"] == "PFI" else TASK08_EXTENSION / "assessments"
        path = root / f"eip-{row['eip']}.yaml"
        record = load_yaml(path)
        assessment = llm_assessment(
            record,
            path=path,
            fork=PROSPECTIVE_FORK,
            mode="prospective",
            revision=2,
            role="primary",
            summary_key="snapshot_scope_summary",
            eip_key="snapshot_eip",
            rubric_key="rubric_source",
            assessor_key="assessor",
        )
        if assessment["score"] != row["score"]:
            raise BuildError(f"Task 08 summary score mismatch for EIP-{row['eip']}")
        assessments.append(assessment)
        sources.append(source(path))
        occurrence = _base_occurrence(
            fork=PROSPECTIVE_FORK, eip=assessment["eip"], title=assessment["title"], layers=record["eip"]["layers"], mode="prospective"
        )
        occurrence["snapshot_status"] = row["snapshot_status"]
        occurrence["llm"] = _llm_summary(assessment)
        occurrence["assessment_ids"].append(assessment["id"])
        occurrences.append(occurrence)
    for row in summary["not_applicable_eips"]:
        occurrence = _base_occurrence(
            fork=PROSPECTIVE_FORK, eip=row["eip"], title=row["title"], layers=row["affected_layers"], mode="prospective"
        )
        occurrence["snapshot_status"] = row["snapshot_status"]
        occurrence["llm"] = {
            "status": STATUS_NOT_APPLICABLE,
            "assessment_id": None,
            "score": None,
            "tier": None,
            "confidence": None,
            "under_specified": None,
            "exclusion_kind": row["exclusion_kind"],
            "rationale": row["rationale"],
            "information_cutoff_at": summary["snapshot"]["information_cutoff_at"],
            "assessed_revision_at": None,
        }
        occurrences.append(occurrence)
    public_summary = {
        "caveats": summary["caveats"],
        "captured_on": summary["snapshot"]["captured_on"],
        "confidence_distribution": summary["distributions"]["confidence"],
        "information_cutoff_at": summary["snapshot"]["information_cutoff_at"],
        "not_applicable": HEGOTA_GATE["not_applicable"],
        "pfi_score_sum": summary["el_rubric_totals"]["original_pfi"]["score_sum"],
        "pfi_scored": summary["el_rubric_totals"]["original_pfi"]["scored_denominator"],
        "sfi_cfi_score_sum": summary["el_rubric_totals"]["sfi_cfi_extension"]["score_sum"],
        "sfi_cfi_scored": summary["el_rubric_totals"]["sfi_cfi_extension"]["scored_denominator"],
        "score_sum": HEGOTA_GATE["total"],
        "scored": HEGOTA_GATE["scored"],
        "snapshot_id": HEGOTA_GATE["snapshot"],
        "source_commit": summary["snapshot"]["commit"],
        "tier_distribution": summary["distributions"]["tiers"],
        "total_entries": HEGOTA_GATE["population"],
        "under_specification_distribution": summary["distributions"]["under_specification"],
    }
    if public_summary["pfi_score_sum"] != 776 or public_summary["pfi_scored"] != 37:
        raise BuildError("Task 08 original PFI subtotal changed")
    return occurrences, assessments, public_summary, sources


def load_amsterdam_human() -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]], list[dict[str, str]]]:
    """Return (assessments, 05c comparison records by EIP, sources) for the Amsterdam human study."""
    assessments: list[dict[str, Any]] = []
    comparisons: dict[int, dict[str, Any]] = {}
    sources: list[dict[str, str]] = []
    human_root = TASK05C / "inputs/human"
    automated_root = TASK05C / "outputs/automated"
    comparison_root = TASK05C / "outputs/comparisons"
    for path in sorted(human_root.glob("eip-*.yaml")):
        record = load_yaml(path)
        assessments.append(human_assessment_from_05c(record, path=path, fork="amsterdam"))
        sources.append(source(path))
    for path in sorted(automated_root.glob("eip-*.yaml")):
        record = load_yaml(path)
        assessments.append(
            llm_assessment(
                record,
                path=path,
                fork="amsterdam",
                mode="retrospective",
                revision=1,
                role="historical_rubric_rerun",
                summary_key="historical_scope_summary",
                eip_key="historical_eip",
                rubric_key="historical_rubric",
                assessor_key="assessor_environment",
            )
        )
        sources.append(source(path))
    for path in sorted(comparison_root.glob("eip-*.yaml")):
        record = load_yaml(path)
        comparisons[record["eip"]["number"]] = record
        sources.append(source(path))
    human_eips = {item["eip"] for item in assessments if item["source"] == SOURCE_HUMAN}
    rerun_eips = {item["eip"] for item in assessments if item["source"] != SOURCE_HUMAN}
    if not (human_eips == rerun_eips == set(comparisons)) or len(human_eips) != 12:
        raise BuildError("Task 05c human, automated, and comparison populations differ")
    return assessments, comparisons, sources


def load_hegota_human(
    titles: dict[int, str], rubric_sources: dict[int, dict[str, Any]]
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    """Return (human status by EIP, human assessments, snapshot summary, sources) from Task 09."""
    snapshot_path = TASK09 / "snapshot.yaml"
    snapshot = load_yaml(snapshot_path)
    sources = [source(snapshot_path)]
    statuses: dict[int, dict[str, Any]] = {}
    assessments: list[dict[str, Any]] = []
    status_map = {"not_yet_available": STATUS_NOT_AVAILABLE}
    for entry in snapshot["entries"]:
        eip = entry["eip"]
        status = status_map.get(entry["human_assessment_status"], entry["human_assessment_status"])
        summary: dict[str, Any] = {
            "status": status,
            "assessment_id": None,
            "score": None,
            "tier": None,
            "rubric_revision": None,
            "source_record": None,
            "other_candidates": [],
            "note": None,
        }
        if entry["preferred_candidate"] is not None:
            path = TASK09 / "assessments" / f"eip-{eip}.yaml"
            record = load_yaml(path)
            sources.append(source(path))
            candidates = record["candidates"]
            preferred = next(item for item in candidates if item["candidate_id"] == entry["preferred_candidate"])
            assessment = human_assessment_from_task09(
                preferred, eip=eip, title=titles[eip], status=status, path=path, rubric_sources=rubric_sources
            )
            assessments.append(assessment)
            summary.update(
                {
                    "assessment_id": assessment["id"],
                    "score": assessment["score"],
                    "tier": assessment["tier"],
                    "rubric_revision": assessment["rubric_revision"],
                    "source_record": assessment["provenance"]["source_record"],
                }
            )
            for candidate in candidates:
                if candidate["candidate_id"] == preferred["candidate_id"]:
                    continue
                origin = candidate["source"]
                summary["other_candidates"].append(
                    {
                        "availability": candidate["availability"],
                        "parse_state": candidate["parse_state"],
                        "rubric_revision": candidate.get("rubric_revision"),
                        "recomputed_total": candidate.get("recomputed_total"),
                        "duplicates_preferred_scores": bool(candidate.get("duplicates_merged_scores")),
                        "pull_request": (
                            {"number": origin["pull_request"], "url": origin["pull_request_url"], "title": origin["pull_request_title"], "draft": origin["draft"]}
                            if origin["kind"] == "open_pull_request"
                            else None
                        ),
                        "immutable_url": origin["immutable_url"],
                    }
                )
        else:
            summary["note"] = "No STEEL checklist existed on the ethspecs/pm default branch or in any open pull request at the snapshot."
        statuses[eip] = summary
    counts = {status_map.get(key, key): value for key, value in snapshot["status_counts"].items()}
    public_snapshot = {
        "snapshot_id": snapshot["snapshot_id"],
        "captured_at": snapshot["captured_at"],
        "upstream": {
            "repository": snapshot["upstream"]["repository"],
            "default_branch": snapshot["upstream"]["default_branch"],
            "head_commit": snapshot["upstream"]["head_commit"],
            "head_committed_at": snapshot["upstream"]["head_committed_at"],
            "assessment_directory": snapshot["upstream"]["assessment_directory"],
            "license": snapshot["upstream"]["license"],
        },
        "status_counts": counts,
        "population": snapshot["population"]["count"],
        "open_pull_requests": [
            {"number": pull["number"], "title": pull["title"], "url": pull["url"], "draft": pull["draft"], "updated_at": pull["updated_at"], "eips": pull["eips"]}
            for pull in snapshot["open_pull_requests"]
        ],
    }
    return statuses, assessments, public_snapshot, sources
