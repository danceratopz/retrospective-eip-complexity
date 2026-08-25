#!/usr/bin/env python3
"""Prepare blinded Task 05c packages by replacing only the Task 05 rubric layer."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from common import (
    ASSESSOR_PROMPT_PATH,
    CONTRACT_PATH,
    INVENTORY_PATH,
    PACKAGE_ROOT,
    REPO_ROOT,
    TASK05_PACKAGE_ROOT,
    TASK_ROOT,
    StudyError,
    aggregate_hash,
    load_yaml,
    rel,
    sha256_file,
    write_bytes,
    write_yaml,
)


def rendered_prompt(number: int) -> bytes:
    source = ASSESSOR_PROMPT_PATH.read_text(encoding="utf-8")
    return (
        f"# Assigned assessment: Amsterdam EIP-{number}\n\n"
        "The identity above and package/manifest.yaml define the sole assigned proposal.\n\n"
        + source
    ).encode()


def output_template(
    number: int,
    inventory_item: dict[str, Any],
    manifest_path: Path,
    rubric: dict[str, Any],
    prompt_path: Path,
    assessment_sources: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task_id": "05c-amsterdam-human-assessment-alignment-automated",
        "fork_id": "amsterdam",
        "eip": copy.deepcopy(inventory_item["eip"]),
        "assessment": {"historical_scope_summary": None},
        "provenance": {
            "input_package": {
                "manifest_path": rel(manifest_path),
                "manifest_sha256": sha256_file(manifest_path),
            },
            "historical_eip": copy.deepcopy(
                load_yaml(REPO_ROOT / inventory_item["task_05_package_manifest"]["path"])[
                    "historical_eip"
                ]
            ),
            "historical_rubric": {
                key: copy.deepcopy(rubric[key])
                for key in (
                    "repository",
                    "commit",
                    "committed_at",
                    "path",
                    "git_blob_sha",
                    "content_sha256",
                    "immutable_url",
                    "anchor_order",
                    "score_domains",
                    "exceptional_score",
                    "maximum_score",
                    "tier_thresholds",
                    "known_source_defects",
                )
            },
            "task_contract": {"path": rel(CONTRACT_PATH), "content_sha256": sha256_file(CONTRACT_PATH)},
            "assessor_prompt": {"path": rel(prompt_path), "content_sha256": sha256_file(prompt_path)},
            "assessor_environment": {
                "codex_executable_path": None,
                "codex_version": None,
                "codex_binary_sha256": None,
                "command": [],
                "model": "gpt-5.6-sol",
                "reasoning_effort": "xhigh",
                "approval_policy": "never",
                "run_at": None,
                "session_id": None,
                "session_id_source": None,
                "isolation_method": None,
                "launcher_path": rel(TASK_ROOT / "scripts/run_isolated.py"),
                "launcher_sha256": sha256_file(TASK_ROOT / "scripts/run_isolated.py"),
                "agent_identity": "Codex",
                "skills_used": [],
                "prohibited_capability_exposure": False,
            },
            "sources_consulted": copy.deepcopy(assessment_sources),
            "operational_files_read": [
                "ASSESSMENT-CONTRACT.md",
                "PROMPT.md",
                "package/manifest.yaml",
                "package/output-template.yaml",
            ],
        },
        "criteria": [
            {
                "id": criterion["id"],
                "label": criterion["label"],
                "definition_present": criterion["definition_present"],
                "allowed_scores": criterion["allowed_scores"],
                "score": None,
                "evidence": [{"source": None, "locator": None, "summary": None}],
                "rationale": None,
                "confidence": None,
                "uncertainty_note": None,
                "exceptional_score_justification": None,
            }
            for criterion in rubric["anchors"]
        ],
        "totals": {
            "primary_score": None,
            "maximum_score": rubric["maximum_score"],
            "maximum_kind": "nominal_24_rows_times_3_exceptional_scores_may_exceed",
            "complexity_tier": None,
            "tier_thresholds": copy.deepcopy(rubric["tier_thresholds"]),
        },
        "under_specification": {
            "present": None,
            "summary": None,
            "affected_criteria": [],
            "plausible_total_range": {"minimum": None, "maximum": None},
            "plausible_tiers": [],
            "unresolved_questions": [],
        },
        "hindsight_control": {
            "internet_access_attempted": False,
            "prohibited_source_exposure": False,
            "contaminated": False,
            "exposure_details": [],
            "package_grounding_attestation": None,
            "latent_knowledge_limitation_acknowledged": None,
        },
        "notable_ambiguities": [],
        "overall_confidence": None,
    }


def prepare_one(item: dict[str, Any]) -> None:
    number = int(item["eip"]["number"])
    source_package = TASK05_PACKAGE_ROOT / f"eip-{number}"
    source_manifest = load_yaml(source_package / "manifest.yaml")
    human = load_yaml(REPO_ROOT / item["human_record"]["path"])
    rubric = human["historical_rubric"]
    package = PACKAGE_ROOT / f"eip-{number}"

    # The source allowlist is copied file-for-file except for rubric.md and the rubric-shaped template.
    for source_name in source_manifest["assessment_source_files"]:
        if source_name == "rubric.md":
            continue
        source = source_package / source_name
        destination = package / source_name
        write_bytes(destination, source.read_bytes())
    rubric_source = REPO_ROOT / rubric["task_path"]
    write_bytes(package / "rubric.md", rubric_source.read_bytes())

    manifest = {
        "schema_version": 1,
        "task_id": "05c-amsterdam-human-assessment-alignment-package",
        "fork_id": "amsterdam",
        "eip": copy.deepcopy(item["eip"]),
        "task_04_ref": copy.deepcopy(source_manifest["task_04_ref"]),
        "task_05_source": {
            "manifest_path": item["task_05_package_manifest"]["path"],
            "manifest_sha256": item["task_05_package_manifest"]["sha256"],
            "reuse_policy": "exact_eip_and_supporting_allowlist_replace_only_rubric_and_output_template",
        },
        "historical_eip": copy.deepcopy(source_manifest["historical_eip"]),
        "historical_rubric": {
            key: copy.deepcopy(rubric[key])
            for key in (
                "repository",
                "commit",
                "committed_at",
                "path",
                "git_blob_sha",
                "content_sha256",
                "immutable_url",
                "task_path",
                "anchor_order",
                "score_domains",
                "exceptional_score",
                "maximum_score",
                "tier_thresholds",
                "known_source_defects",
            )
        },
        "supporting_documents": copy.deepcopy(source_manifest.get("supporting_documents", [])),
        "provenance_only_links": copy.deepcopy(source_manifest.get("provenance_only_links", [])),
        "assessment_source_files": copy.deepcopy(source_manifest["assessment_source_files"]),
        "source_policy": {
            "internet_allowed": False,
            "follow_links_allowed": False,
            "files_outside_package_allowed": False,
            "dedicated_assessment_skill_allowed": False,
            "human_assessment_allowed": False,
            "current_rubric_or_score_allowed": False,
            "implementations_tests_devnets_outcomes_allowed": False,
        },
        "preparation": {
            "script": rel(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "assessor_prompt_source_sha256": sha256_file(ASSESSOR_PROMPT_PATH),
        },
    }
    manifest_path = package / "manifest.yaml"
    write_yaml(manifest_path, manifest)

    prompt_path = TASK_ROOT / f"prompts/rendered/eip-{number}.md"
    write_bytes(prompt_path, rendered_prompt(number))
    template = output_template(number, item, manifest_path, rubric, prompt_path, manifest["assessment_source_files"])
    write_yaml(package / "output-template.yaml", template)

    paths = [path for path in package.rglob("*") if path.is_file()]
    package_hash, _ = aggregate_hash(paths, package)
    print(
        f"prepared EIP-{number}: sources={len(manifest['assessment_source_files'])} "
        f"criteria={len(template['criteria'])} package={package_hash[:12]}"
    )


def main() -> int:
    inventory = load_yaml(INVENTORY_PATH)
    included = [item for item in inventory["eips"] if item["status"] == "included"]
    if not included:
        raise StudyError("Study inventory has no included EIPs")
    for item in included:
        prepare_one(item)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StudyError as error:
        raise SystemExit(f"preparation error: {error}") from error
