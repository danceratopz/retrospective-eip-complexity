#!/usr/bin/env python3
"""Derive the Amsterdam study population and reconstruct historical human events."""

from __future__ import annotations

import argparse
import copy
import re
from pathlib import Path
from typing import Any

from common import (
    APPROVED_ROOT,
    CRITERIA,
    EIPS_REPO,
    HUMAN_ROOT,
    INVENTORY_PATH,
    MATERIAL_HUMAN_CLASSES,
    PM_REPO,
    REPO_ROOT,
    RUBRIC_ROOT,
    TASK05_OUTPUT_ROOT,
    TASK05_PACKAGE_ROOT,
    TASK_ROOT,
    StudyError,
    extract_human_scores,
    git_blob,
    git_commit_time,
    git_path_exists,
    git_text,
    human_score_fingerprint,
    latest_path_commit_at,
    load_yaml,
    now,
    parse_time,
    record_payload_hash,
    rel,
    repo_identity,
    rubric_semantics,
    sha256_bytes,
    sha256_file,
    write_bytes,
    write_yaml,
)


LEGACY_HUMAN_PATHS = {8024: ["complexity_assessments/EIPs/eip8024.md"]}

# These are evidence classifications, not score adjustments.  They are deliberately
# fixed before the B-versus-C comparison stage and cite only the historical human file.
EXPOSURE = {
    2780: (
        "possible_exposure",
        "The rationale discusses existing EIP-7702 tests needing updates, indicating awareness of a concrete test corpus but not a completed implementation of EIP-2780.",
    ),
    7610: (
        "possible_exposure",
        "The assessment cites a Magicians observation and possible EELS work, but describes the implementation as prospective.",
    ),
    7708: (
        "high_exposure",
        "The rationale describes the then-current execution-specs test-framework handling of transition-tool logs and a required enhancement.",
    ),
    7778: (
        "low_exposure",
        "The assessment uses proposal-level reasoning about refunds and block gas limits without identifying an implementation, devnet, or completed test effort.",
    ),
    7843: (
        "low_exposure",
        "The assessment describes required future interface fields and does not identify implementation or test outcomes.",
    ),
    7928: (
        "high_exposure",
        "The assessment explicitly relies on implementation files, permanent framework additions, benchmarks, planned and completed tests, spec churn, and bugs found by tests.",
    ),
    7976: (
        "high_exposure",
        "The assessment says generators were already prepared and refers to work completed during EIP-7623 testing and existing static tests.",
    ),
    7981: (
        "high_exposure",
        "The assessment reasons from an existing intrinsic-gas calculator interface used by many access-list tests.",
    ),
    7997: (
        "low_exposure",
        "The assessment is grounded in proposal mechanisms and a disclosed security concern, with no implementation, devnet, or test-outcome evidence.",
    ),
    8024: (
        "low_exposure",
        "The client-performance comment is hypothetical and the assessment identifies no visible implementation, devnet, or completed test evidence.",
    ),
    8037: (
        "high_exposure",
        "The assessment links the execution-specs static-test tree and describes rework of existing Python tests.",
    ),
    8038: (
        "possible_exposure",
        "The assessment notes that benchmark numbers were not yet available, showing fork-development awareness without reporting completed implementation outcomes.",
    ),
}


def human_paths(number: int) -> list[str]:
    return [
        f"complexity_assessments/EIPs/EIP-{number}.md",
        *LEGACY_HUMAN_PATHS.get(number, []),
    ]


def current_human_path(number: int) -> str | None:
    for path in human_paths(number):
        if git_path_exists(PM_REPO, "HEAD", path):
            return path
    return None


def commit_file(repo: Path, commit: str, paths: list[str]) -> tuple[str, bytes, str] | None:
    for path in paths:
        if git_path_exists(repo, commit, path):
            payload, blob = git_blob(repo, commit, path)
            return path, payload, blob
    return None


def row_fingerprint(fingerprint: dict[str, Any] | None) -> tuple[Any, ...] | None:
    if fingerprint is None:
        return None
    return tuple(
        (row["id"], row["raw"], row["rationale"])
        for row in fingerprint["rows"]
    ) + (
        fingerprint["total"],
        fingerprint["tier"],
        fingerprint["special"],
        fingerprint["notes"],
    )


def classify_human_history(number: int) -> list[dict[str, Any]]:
    paths = human_paths(number)
    raw = git_text(
        PM_REPO,
        "log",
        "--all",
        "--full-history",
        "--format=%H",
        "--",
        *paths,
    )
    commits = list(dict.fromkeys(line.strip() for line in raw.splitlines() if line.strip()))
    records: list[dict[str, Any]] = []
    for commit in commits:
        resolved = commit_file(PM_REPO, commit, paths)
        if resolved is None:
            continue
        path, payload, blob = resolved
        text = payload.decode()
        fingerprint = human_score_fingerprint(text)
        if fingerprint is None:
            continue
        parents = git_text(PM_REPO, "show", "-s", "--format=%P", commit).strip().split()
        parent_values: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for parent in parents:
            parent_resolved = commit_file(PM_REPO, parent, paths)
            if parent_resolved is None:
                continue
            parent_text = parent_resolved[1].decode()
            parent_fingerprint = human_score_fingerprint(parent_text)
            if parent_fingerprint is not None:
                parent_values.append((parent_fingerprint, rubric_semantics(parent_text)))

        current_rows = [(row["id"], row["raw"]) for row in fingerprint["rows"]]
        subject = git_text(PM_REPO, "show", "-s", "--format=%s", commit).strip()
        classification: str
        evidence: str
        if subject == 'Rename checklist "anchors" to "criteria"':
            classification = "title_link_formatting_or_editorial_change"
            evidence = "Campaign-wide terminology-only rename; scores, rationales, definitions, domains, and thresholds are unchanged."
        elif not parent_values:
            classification = "initial_substantive_scoring"
            evidence = "The commit first establishes a complete checklist with published score content."
        elif any(row_fingerprint(value[0]) == row_fingerprint(fingerprint) for value in parent_values):
            classification = "title_link_formatting_or_editorial_change"
            evidence = "At least one parent already contains the identical score/rationale fingerprint."
        else:
            prior_fingerprint, prior_semantics = parent_values[0]
            prior_rows = [(row["id"], row["raw"]) for row in prior_fingerprint["rows"]]
            if prior_rows != current_rows or prior_fingerprint["total"] != fingerprint["total"]:
                classification = "substantive_score_change"
                evidence = "One or more raw score cells or the published total changed."
            elif row_fingerprint(prior_fingerprint) != row_fingerprint(fingerprint):
                classification = "substantive_rationale_change"
                evidence = "Score rationales, special considerations, or assessment notes changed."
            elif prior_semantics != rubric_semantics(text):
                classification = "rubric_or_anchor_definition_change"
                evidence = "The embedded rubric semantics changed while assessment values did not."
            else:
                classification = "title_link_formatting_or_editorial_change"
                evidence = "Only title, link, formatting, terminology, or other non-scoring content changed."

        records.append(
            {
                "commit": commit,
                "committed_at": git_commit_time(PM_REPO, commit),
                "subject": subject,
                "path": path,
                "git_blob_sha": blob,
                "content_sha256": sha256_bytes(payload),
                "classification": classification,
                "classification_evidence": evidence,
                "immutable_url": f"https://github.com/ethspecs/pm/blob/{commit}/{path}",
            }
        )
    records.sort(key=lambda item: (parse_time(item["committed_at"]), item["commit"]))
    return records


def select_human_event(history: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [item for item in history if item["classification"] in MATERIAL_HUMAN_CLASSES]
    if not candidates:
        raise StudyError("No substantive human scoring event was found")
    return max(candidates, key=lambda item: (parse_time(item["committed_at"]), item["commit"]))


def rubric_record(event: dict[str, Any], human_text: str) -> tuple[dict[str, Any], str]:
    commit = latest_path_commit_at(PM_REPO, "Templates/EIP-Complexity-Assessment.md", event["committed_at"])
    path = "Templates/EIP-Complexity-Assessment.md"
    payload, blob = git_blob(PM_REPO, commit, path)
    text = payload.decode()
    semantics = rubric_semantics(text)
    output_name = f"template-{commit}.md"
    output = RUBRIC_ROOT / output_name
    write_bytes(output, payload)
    human_semantics = rubric_semantics(human_text)
    if human_semantics == semantics:
        match = "exact"
        rationale = "Anchor inventory, definitions, score domains, nominal maximum, and thresholds match."
    else:
        # A compatible result may differ in presentation, but the parser has already removed headings,
        # table formatting, score cells, and assessment prose from the semantic representation.
        template_core = copy.deepcopy(semantics)
        human_core = copy.deepcopy(human_semantics)
        for candidate in (template_core, human_core):
            for criterion in candidate["criteria"]:
                if isinstance(criterion.get("definition"), str):
                    criterion["definition"] = re.sub(r"\s+", " ", criterion["definition"]).strip()
        if template_core == human_core:
            match = "compatible"
            rationale = "Only non-semantic whitespace or presentation differs."
        else:
            match = "divergent"
            rationale = "At least one scoring-relevant rubric semantic differs."
    record = {
        "repository": "ethspecs/pm",
        "commit": commit,
        "committed_at": git_commit_time(PM_REPO, commit),
        "path": path,
        "git_blob_sha": blob,
        "content_sha256": sha256_bytes(payload),
        "immutable_url": f"https://github.com/ethspecs/pm/blob/{commit}/{path}",
        "task_path": rel(output),
        "anchor_order": [item["id"] for item in semantics["criteria"]],
        "anchors": semantics["criteria"],
        "score_domains": {item["id"]: item["base_allowed_scores"] for item in semantics["criteria"]},
        "exceptional_score": semantics["exceptional_score"],
        "maximum_score": semantics["nominal_maximum"],
        "tier_thresholds": semantics["tier_thresholds"],
        "known_source_defects": [
            "The checklist contains Engine API encoding changes but the template has no dedicated definition for that row."
        ],
    }
    manifest_path = RUBRIC_ROOT / f"template-{commit}.yaml"
    manifest = copy.deepcopy(record)
    manifest["schema_version"] = 1
    manifest["task_id"] = "05c-historical-rubric"
    write_yaml(manifest_path, manifest)
    record["manifest_path"] = rel(manifest_path)
    record["manifest_sha256"] = sha256_file(manifest_path)
    return record, match + ": " + rationale


def task01_intervening(number: int, selected_commit: str, human_commit: str) -> tuple[list[dict[str, Any]], str, str]:
    history_path = REPO_ROOT / f"research/tasks/01-fork-eip-history/outputs/eips/eip-{number}.yaml"
    history = load_yaml(history_path)
    events = history["revision_history"]["events"]
    by_commit = {item["commit"]: item for item in events}
    if selected_commit not in by_commit or human_commit not in by_commit:
        raise StudyError(f"Task 01 history does not contain both EIP-{number} endpoint commits")
    selected_time = parse_time(by_commit[selected_commit]["committed_at"])
    human_time = parse_time(by_commit[human_commit]["committed_at"])
    if human_time < selected_time:
        return [], "unknown", "The human-time EIP commit predates the approved Task 04 commit."
    intervening = [
        copy.deepcopy(item)
        for item in events
        if selected_time < parse_time(item["committed_at"]) <= human_time
    ]
    if selected_commit == human_commit:
        alignment = "exact_blob"
        summary = "The human-time and approved Task 04 EIP commits resolve to the same Git blob."
    elif any(item["semantic_effect"] == "uncertain" for item in intervening):
        alignment = "unknown"
        summary = "At least one intervening EIP revision has an uncertain semantic classification."
    elif any(item["semantic_effect"] == "substantive" for item in intervening):
        alignment = "substantive_drift"
        summaries = [item["summary"] for item in intervening if item["semantic_effect"] == "substantive"]
        summary = "Substantive intervening revisions: " + " | ".join(summaries)
    else:
        alignment = "no_substantive_drift"
        summary = "Every intervening EIP revision is classified non-substantive by Task 01."
    return intervening, alignment, summary


def reconstruct_human(number: int, ref: dict[str, Any]) -> dict[str, Any]:
    history = classify_human_history(number)
    event = select_human_event(history)
    human_payload, human_blob = git_blob(PM_REPO, event["commit"], event["path"])
    human_text = human_payload.decode()
    rubric, match_detail = rubric_record(event, human_text)
    match, match_rationale = match_detail.split(": ", 1)
    scores = extract_human_scores(human_text, rubric_semantics(human_text))

    eip_path = f"EIPS/eip-{number}.md"
    human_eip_commit = latest_path_commit_at(EIPS_REPO, eip_path, event["committed_at"])
    human_eip_payload, human_eip_blob = git_blob(EIPS_REPO, human_eip_commit, eip_path)
    selected = ref["selection"]["selected_revision"]
    intervening, alignment, alignment_summary = task01_intervening(
        number, selected["commit"], human_eip_commit
    )
    exposure, exposure_rationale = EXPOSURE[number]
    unresolved: list[str] = []
    if not scores["numeric_total_unambiguous"]:
        unresolved.append("The human total or tier is not mechanically unambiguous.")
    if match not in {"exact", "compatible"}:
        unresolved.append("The embedded human rubric does not cleanly match the time-resolved template.")
    record: dict[str, Any] = {
        "schema_version": 1,
        "task_id": "05c-amsterdam-human-assessment-alignment-human",
        "eip": copy.deepcopy(ref["eip"]),
        "human_event": {
            "repository": "ethspecs/pm",
            "commit": event["commit"],
            "committed_at": event["committed_at"],
            "path": event["path"],
            "git_blob_sha": human_blob,
            "content_sha256": sha256_bytes(human_payload),
            "immutable_url": event["immutable_url"],
            "selection_rule": "latest substantive score or rationale event in the complete reachable file history",
            "selection_evidence": event["classification_evidence"],
        },
        "commit_history": history,
        **scores,
        "historical_rubric": rubric,
        "template_match": {
            "classification": match,
            "rationale": match_rationale,
        },
        "human_time_eip": {
            "repository": "ethereum/EIPs",
            "commit": human_eip_commit,
            "committed_at": git_commit_time(EIPS_REPO, human_eip_commit),
            "path": eip_path,
            "git_blob_sha": human_eip_blob,
            "content_sha256": sha256_bytes(human_eip_payload),
            "immutable_url": f"https://github.com/ethereum/EIPs/blob/{human_eip_commit}/{eip_path}",
        },
        "approved_task_04_eip": copy.deepcopy(selected),
        "intervening_eip_commits": intervening,
        "input_alignment": {
            "classification": alignment,
            "summary": alignment_summary,
            "classification_source": rel(
                REPO_ROOT / f"research/tasks/01-fork-eip-history/outputs/eips/eip-{number}.yaml"
            ),
        },
        "human_timing_exposure": {
            "classification": exposure,
            "rationale": exposure_rationale,
            "evidence_source": "the exact historical human assessment blob",
        },
        "evidence_locators": [
            event["immutable_url"],
            rubric["immutable_url"],
            f"https://github.com/ethereum/EIPs/blob/{human_eip_commit}/{eip_path}",
        ],
        "confidence": "high" if match == "exact" and alignment != "unknown" else "medium",
        "unresolved_issues": unresolved,
        "generation": {
            "script": rel(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "generated_at": now(),
            "record_payload_sha256": None,
        },
    }
    record["generation"]["record_payload_sha256"] = record_payload_hash(record)
    return record


def basic_task05_status(number: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    package = TASK05_PACKAGE_ROOT / f"eip-{number}"
    output = TASK05_OUTPUT_ROOT / f"eip-{number}.yaml"
    manifest_path = package / "manifest.yaml"
    if not manifest_path.is_file():
        reasons.append("missing_task_05_package")
    if not output.is_file():
        reasons.append("missing_task_05_output")
    if not reasons:
        manifest = load_yaml(manifest_path)
        result = load_yaml(output)
        if int(manifest.get("eip", {}).get("number", -1)) != number:
            reasons.append("invalid_task_05_package_identity")
        if int(result.get("eip", {}).get("number", -1)) != number:
            reasons.append("invalid_task_05_output_identity")
        if result.get("hindsight_control", {}).get("contaminated") is not False:
            reasons.append("invalid_or_contaminated_task_05_output")
    return not reasons, reasons


def build_inventory() -> dict[str, Any]:
    repositories = {name: repo_identity(name) for name in ("research", "pm", "eips")}
    records: list[dict[str, Any]] = []
    for ref_path in sorted(APPROVED_ROOT.glob("eip-*.yaml")):
        ref = load_yaml(ref_path)
        number = int(ref["eip"]["number"])
        if ref.get("review", {}).get("status") != "approved":
            raise StudyError(f"Amsterdam Task 04 ref is not approved: {ref_path}")
        human_path = current_human_path(number)
        task05_valid, task05_reasons = basic_task05_status(number)
        reasons: list[str] = []
        if human_path is None:
            reasons.append("no_historical_human_assessment")
        reasons.extend(task05_reasons)
        record: dict[str, Any] = {
            "eip": copy.deepcopy(ref["eip"]),
            "status": "excluded" if reasons else "included",
            "exclusion_reasons": reasons,
            "task_04_ref": {"path": rel(ref_path), "sha256": sha256_file(ref_path)},
            "task_05_package_manifest": {
                "path": rel(TASK05_PACKAGE_ROOT / f"eip-{number}/manifest.yaml"),
                "sha256": (
                    sha256_file(TASK05_PACKAGE_ROOT / f"eip-{number}/manifest.yaml")
                    if (TASK05_PACKAGE_ROOT / f"eip-{number}/manifest.yaml").is_file()
                    else None
                ),
            },
            "task_05_output": {
                "path": rel(TASK05_OUTPUT_ROOT / f"eip-{number}.yaml"),
                "sha256": (
                    sha256_file(TASK05_OUTPUT_ROOT / f"eip-{number}.yaml")
                    if (TASK05_OUTPUT_ROOT / f"eip-{number}.yaml").is_file()
                    else None
                ),
                "valid_at_discovery": task05_valid,
            },
            "pm_human_assessment_path": human_path,
        }
        if not reasons:
            human_record = reconstruct_human(number, ref)
            human_output = HUMAN_ROOT / f"eip-{number}.yaml"
            write_yaml(human_output, human_record)
            failed: list[str] = []
            if human_record["input_alignment"]["classification"] not in {
                "exact_blob",
                "no_substantive_drift",
            }:
                failed.append("substantive_or_unknown_eip_input_drift")
            if human_record["template_match"]["classification"] not in {"exact", "compatible"}:
                failed.append("divergent_or_unknown_historical_template")
            if not human_record["numeric_total_unambiguous"]:
                failed.append("ambiguous_human_total_or_tier")
            record.update(
                {
                    "human_record": {"path": rel(human_output), "sha256": sha256_file(human_output)},
                    "selected_human_event": copy.deepcopy(human_record["human_event"]),
                    "resolved_historical_rubric": copy.deepcopy(human_record["historical_rubric"]),
                    "input_alignment": human_record["input_alignment"]["classification"],
                    "template_match": human_record["template_match"]["classification"],
                    "human_timing_exposure": human_record["human_timing_exposure"]["classification"],
                    "clean_comparison_eligible": not failed,
                    "clean_comparison_failed_conditions": failed,
                    "low_exposure_comparison_eligible": not failed
                    and human_record["human_timing_exposure"]["classification"] == "low_exposure",
                    "expected_paths": {
                        "package": rel(TASK_ROOT / f"inputs/packages/eip-{number}"),
                        "automated": rel(TASK_ROOT / f"outputs/automated/eip-{number}.yaml"),
                        "comparison": rel(TASK_ROOT / f"outputs/comparisons/eip-{number}.yaml"),
                    },
                }
            )
        records.append(record)

    inventory: dict[str, Any] = {
        "schema_version": 1,
        "task_id": "05c-amsterdam-human-assessment-alignment",
        "task_version": "1.0.0",
        "fork_id": "amsterdam",
        "generated_at": now(),
        "generation_script": {"path": rel(Path(__file__)), "sha256": sha256_file(Path(__file__))},
        "source_repositories": repositories,
        "population_rule": "approved Task 04 Amsterdam refs intersect completed PM human assessments and valid Task 05 packages/outputs",
        "counts": {
            "approved_task_04": len(records),
            "included": sum(item["status"] == "included" for item in records),
            "excluded": sum(item["status"] == "excluded" for item in records),
            "clean": sum(item.get("clean_comparison_eligible", False) for item in records),
        },
        "eips": records,
    }
    return inventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="regenerate in memory and require byte identity")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory = build_inventory()
    payload = __import__("common").yaml_bytes(inventory)
    if args.check:
        if not INVENTORY_PATH.is_file() or INVENTORY_PATH.read_bytes() != payload:
            raise StudyError("Study inventory is stale or not byte-identical")
    else:
        write_bytes(INVENTORY_PATH, payload)
    print(
        f"study inventory: approved={inventory['counts']['approved_task_04']} "
        f"included={inventory['counts']['included']} excluded={inventory['counts']['excluded']} "
        f"clean={inventory['counts']['clean']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StudyError as error:
        raise SystemExit(f"discovery error: {error}") from error
