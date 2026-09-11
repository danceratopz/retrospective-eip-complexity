#!/usr/bin/env python3
"""Validate one completed Task 08 prospective complexity assessment."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from engine_adapter import TASK_ROOT, output_engine, package_engine
from validate_packages import NAMESPACE, PACKAGE_ROOT


OUTPUT_ROOT = TASK_ROOT / "outputs" / "assessments" / NAMESPACE
PROMPT_ROOT = TASK_ROOT / "inputs" / "prompts" / NAMESPACE
RAW_ROOT = TASK_ROOT / "outputs" / "raw" / NAMESPACE
EXPECTED_TASK_ID = "08-hegota-prospective-complexity-assessment"
EXPECTED_FORK_ID = "hegota"
EXPECTED_SNAPSHOT_ID = "hegota-pfi-2026-08-26-ac450a4"
CONFIDENCE = output_engine.CONFIDENCE
BINARY_CRITERIA = output_engine.BINARY_CRITERIA
require_text = output_engine.require_text
tier = output_engine.tier
tiers_in_range = output_engine.tiers_in_range
load_yaml = package_engine.load_yaml
sha256_file = package_engine.file_sha256


class ValidationError(RuntimeError):
    """Raised when an assessment violates the Task 08 contract."""


def package_paths(_fork_id: str, number: int) -> tuple[Path, Path, Path, Path]:
    package = PACKAGE_ROOT / f"eip-{number}"
    output = OUTPUT_ROOT / f"eip-{number}.yaml"
    prompt = PROMPT_ROOT / f"eip-{number}.md"
    return package, output, prompt, package / "output-template.yaml"


def validate(_fork_id: str, number: int, output_override: Path | None = None) -> Path:
    package, default_output, prompt_path, template_path = package_paths("hegota", number)
    output_path = output_override or default_output
    if not output_path.is_file():
        raise ValidationError(f"Missing output: {output_path}")
    manifest_path = package / "manifest.yaml"
    manifest = load_yaml(manifest_path)
    expected = load_yaml(template_path)
    result = load_yaml(output_path)

    if (
        result.get("schema_version") != 1
        or result.get("task_id") != EXPECTED_TASK_ID
        or result.get("fork_id") != EXPECTED_FORK_ID
        or result.get("snapshot_id") != EXPECTED_SNAPSHOT_ID
    ):
        raise ValidationError("Unexpected schema, task, fork, or snapshot identity")
    if int(result.get("eip", {}).get("number", -1)) != number:
        raise ValidationError("EIP identity mismatch")
    if result.get("eip") != expected.get("eip"):
        raise ValidationError("EIP identity fields differ from the sealed template")
    if "historical_scope_summary" in result.get("assessment", {}):
        raise ValidationError("Task 08 must not persist historical scope fields")

    immutable_provenance = [
        "input_package",
        "cohort_snapshot",
        "snapshot_eip",
        "rubric_source",
        "assessor_view",
        "task_contract",
        "assessment_contract",
        "session_prompt",
    ]
    for field in immutable_provenance:
        if result.get("provenance", {}).get(field) != expected["provenance"][field]:
            raise ValidationError(f"Immutable provenance changed: provenance.{field}")
    if expected["provenance"]["input_package"]["manifest_sha256"] != sha256_file(
        manifest_path
    ):
        raise ValidationError("Package manifest hash no longer matches the template")
    if expected["provenance"]["session_prompt"]["content_sha256"] != sha256_file(
        prompt_path
    ):
        raise ValidationError("Session prompt hash no longer matches the template")

    assessor = result.get("provenance", {}).get("assessor", {})
    if assessor.get("model") != "gpt-5.6-sol" or assessor.get("reasoning_effort") != "xhigh":
        raise ValidationError("Assessor model must be gpt-5.6-sol at xhigh")
    for field in (
        "run_at",
        "session_id",
        "session_id_source",
        "isolation_method",
        "agent_identity",
    ):
        require_text(assessor.get(field), f"provenance.assessor.{field}")
    if assessor["session_id_source"] != "isolated_launcher_run_id":
        raise ValidationError("session_id_source must identify the isolated launcher")
    if not assessor["session_id"].startswith("assessment-run-"):
        raise ValidationError("session_id must be populated by the isolated launcher")
    if assessor["isolation_method"] != "bubblewrap_one_eip_capsule_v1":
        raise ValidationError("Unexpected filesystem-isolation method")
    if assessor.get("prohibited_skill_exposure") is not False or assessor.get("skills_used") != []:
        raise ValidationError("Skills must not be exposed or used")

    expected_sources = manifest.get("assessment_source_files")
    if result.get("provenance", {}).get("sources_consulted") != expected_sources:
        raise ValidationError("sources_consulted differs from the sealed allowlist")
    expected_operational = expected["provenance"]["operational_files_read"]
    if result.get("provenance", {}).get("operational_files_read") != expected_operational:
        raise ValidationError("operational_files_read changed")

    raw_output = result.get("provenance", {}).get("assessor_raw_output")
    if raw_output is not None:
        if not isinstance(raw_output, dict):
            raise ValidationError("assessor_raw_output must be a mapping")
        require_text(raw_output.get("path"), "provenance.assessor_raw_output.path")
        require_text(raw_output.get("content_sha256"), "provenance.assessor_raw_output.content_sha256")
        raw_path = (TASK_ROOT / raw_output["path"]).resolve()
        raw_root = RAW_ROOT.resolve()
        if not raw_path.is_relative_to(raw_root) or not raw_path.is_file():
            raise ValidationError("assessor_raw_output does not resolve under Task 08 outputs/raw")
        if sha256_file(raw_path) != raw_output["content_sha256"]:
            raise ValidationError("assessor_raw_output hash mismatch")
        postprocessing = result.get("provenance", {}).get("postprocessing")
        if not isinstance(postprocessing, list) or not postprocessing:
            raise ValidationError("Normalized output must record postprocessing provenance")

    require_text(
        result.get("assessment", {}).get("snapshot_scope_summary"),
        "assessment.snapshot_scope_summary",
    )
    expected_criteria = expected.get("criteria", [])
    criteria = result.get("criteria")
    if not isinstance(criteria, list) or len(criteria) != 28:
        raise ValidationError("Expected exactly 28 criteria")
    total = 0
    for index, (criterion, expected_criterion) in enumerate(zip(criteria, expected_criteria)):
        prefix = f"criteria[{index}]"
        if not isinstance(criterion, dict):
            raise ValidationError(f"{prefix} must be a mapping")
        if criterion.get("id") != expected_criterion["id"]:
            raise ValidationError(f"{prefix}.id is out of canonical order")
        if criterion.get("label") != expected_criterion["label"]:
            raise ValidationError(f"{prefix}.label changed")
        score = criterion.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or score < 0:
            raise ValidationError(f"{prefix}.score must be a non-negative integer")
        if criterion["id"] != "cross_eip_interactions" and score > 4:
            raise ValidationError(f"{prefix}.score exceeds the exceptional maximum")
        if criterion["id"] in BINARY_CRITERIA and score not in {0, 3, 4}:
            raise ValidationError(f"{prefix}.score violates the binary rubric anchors")
        if score == 4 and criterion["id"] != "cross_eip_interactions":
            require_text(
                criterion.get("exceptional_score_justification"),
                f"{prefix}.exceptional_score_justification",
            )
        evidence = criterion.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValidationError(f"{prefix}.evidence must contain a locator")
        for evidence_index, item in enumerate(evidence):
            if not isinstance(item, dict):
                raise ValidationError(f"{prefix}.evidence[{evidence_index}] must be a mapping")
            if item.get("source") not in expected_sources:
                raise ValidationError(f"{prefix}.evidence[{evidence_index}] uses a non-package source")
            require_text(item.get("locator"), f"{prefix}.evidence[{evidence_index}].locator")
            require_text(item.get("summary"), f"{prefix}.evidence[{evidence_index}].summary")
        require_text(criterion.get("rationale"), f"{prefix}.rationale")
        if criterion.get("confidence") not in CONFIDENCE:
            raise ValidationError(f"{prefix}.confidence is invalid")
        require_text(criterion.get("uncertainty_note"), f"{prefix}.uncertainty_note")
        if criterion["id"] == "cross_eip_interactions":
            interactions = criterion.get("interacting_eips")
            unidentified = criterion.get("unidentified_interactions", [])
            if not isinstance(interactions, list) or not isinstance(unidentified, list):
                raise ValidationError(f"{prefix} interaction fields must be lists")
            if any(not isinstance(item, str) or not item.strip() for item in unidentified):
                raise ValidationError(f"{prefix}.unidentified_interactions is invalid")
            if score > 0 and not interactions and not unidentified:
                raise ValidationError(f"{prefix} must identify or describe an interaction")
            if score == 0 and unidentified:
                raise ValidationError(f"{prefix} has unidentified interactions at score zero")
            if any(
                not isinstance(item, int) or isinstance(item, bool) or item == number
                for item in interactions
            ):
                raise ValidationError(f"{prefix}.interacting_eips is invalid")
            if len(interactions) != len(set(interactions)):
                raise ValidationError(f"{prefix}.interacting_eips contains duplicates")
        total += score

    totals = result.get("totals", {})
    if totals.get("primary_score") != total:
        raise ValidationError(f"primary_score must equal criterion sum {total}")
    expected_tier = tier(total)
    if totals.get("complexity_tier") != expected_tier:
        raise ValidationError(f"complexity_tier must be {expected_tier}")

    under = result.get("under_specification", {})
    if not isinstance(under.get("present"), bool):
        raise ValidationError("under_specification.present must be boolean")
    require_text(under.get("summary"), "under_specification.summary")
    affected = under.get("affected_criteria")
    valid_ids = {item["id"] for item in expected_criteria}
    if not isinstance(affected, list) or not set(affected).issubset(valid_ids):
        raise ValidationError("under_specification.affected_criteria is invalid")
    plausible = under.get("plausible_total_range", {})
    minimum, maximum = plausible.get("minimum"), plausible.get("maximum")
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        raise ValidationError("plausible_total_range values must be integers")
    if minimum > total or maximum < total or minimum > maximum:
        raise ValidationError("plausible_total_range must contain the primary score")
    plausible_tiers = under.get("plausible_tiers")
    if plausible_tiers != tiers_in_range(minimum, maximum):
        raise ValidationError("plausible_tiers does not match the stated range")
    if not isinstance(under.get("unresolved_questions"), list):
        raise ValidationError("under_specification.unresolved_questions must be a list")

    control = result.get("information_control", {})
    for field in (
        "internet_access_attempted",
        "post_snapshot_information_exposure",
        "prohibited_source_exposure",
        "contaminated",
    ):
        if control.get(field) is not False:
            raise ValidationError(f"information_control.{field} prevents completion")
    if control.get("exposure_details") != []:
        raise ValidationError("exposure_details must be empty")
    require_text(control.get("attestation"), "information_control.attestation")
    if "hindsight_control" in result:
        raise ValidationError("Task 08 must not persist hindsight_control")
    if not isinstance(result.get("notable_ambiguities"), list):
        raise ValidationError("notable_ambiguities must be a list")
    if result.get("overall_confidence") not in CONFIDENCE:
        raise ValidationError("overall_confidence is invalid")

    print(f"valid Hegota EIP-{number}: total={total} tier={expected_tier}")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eip", required=True, type=int)
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate("hegota", args.eip, args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValidationError, output_engine.ValidationError, KeyError, TypeError) as error:
        raise SystemExit(f"validation error: {error}") from error
