#!/usr/bin/env python3
"""Validate one completed Task 05 retrospective complexity assessment."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import yaml


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
CONFIDENCE = {"low", "medium", "high"}
BINARY_CRITERIA = {
    "modified_opcodes",
    "encoding_changes_rlp_ssz",
    "new_transaction_types",
    "new_block_header_fields",
    "new_fork_activation_mechanism",
}


class ValidationError(RuntimeError):
    """Raised when an assessment output violates the Task 05 contract."""


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"Expected a YAML mapping: {path}")
    return data


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_text(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")


def tier(total: int) -> str:
    if total < 12:
        return "low"
    if total < 23:
        return "medium"
    return "high"


def tiers_in_range(minimum: int, maximum: int) -> list[str]:
    return [
        candidate
        for candidate, lower, upper in (
            ("low", 0, 11),
            ("medium", 12, 22),
            ("high", 23, None),
        )
        if maximum >= lower and (upper is None or minimum <= upper)
    ]


def package_paths(fork_id: str, number: int) -> tuple[Path, Path, Path, Path]:
    package = TASK_ROOT / "inputs" / "fork-eips" / fork_id / f"eip-{number}"
    output = TASK_ROOT / "outputs" / "fork-eips" / fork_id / f"eip-{number}.yaml"
    prompt = TASK_ROOT / "prompts" / fork_id / f"eip-{number}.md"
    template = package / "output-template.yaml"
    return package, output, prompt, template


def validate(fork_id: str, number: int, output_override: Path | None = None) -> Path:
    package, default_output_path, prompt_path, template_path = package_paths(fork_id, number)
    output_path = output_override or default_output_path
    if not output_path.is_file():
        raise ValidationError(f"Missing output: {output_path}")
    manifest_path = package / "manifest.yaml"
    manifest = load_yaml(manifest_path)
    expected = load_yaml(template_path)
    result = load_yaml(output_path)

    if result.get("schema_version") != 1 or result.get("task_id") != expected["task_id"]:
        raise ValidationError("Unexpected schema_version or task_id")
    if result.get("fork_id") != fork_id or int(result.get("eip", {}).get("number", -1)) != number:
        raise ValidationError("Fork or EIP identity mismatch")
    if result.get("eip") != expected["eip"]:
        raise ValidationError("EIP identity fields differ from the sealed template")

    immutable_provenance = [
        "input_package",
        "historical_eip",
        "rubric_source",
        "assessor_view",
        "task_contract",
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
        raise ValidationError("Unexpected or missing filesystem-isolation method")
    if assessor.get("prohibited_skill_exposure") is not False:
        raise ValidationError("Prohibited skill exposure prevents completion")
    skills = assessor.get("skills_used")
    if skills != []:
        raise ValidationError("skills_used must be empty in an isolated Task 05 run")

    expected_sources = manifest.get("assessment_source_files")
    actual_sources = result.get("provenance", {}).get("sources_consulted")
    if actual_sources != expected_sources:
        raise ValidationError(
            "sources_consulted must equal the sealed assessment_source_files in manifest order"
        )
    expected_operational = expected.get("provenance", {}).get("operational_files_read")
    if expected_operational is not None:
        actual_operational = result.get("provenance", {}).get("operational_files_read")
        if actual_operational != expected_operational:
            raise ValidationError(
                "operational_files_read must preserve the sealed template value"
            )

    raw_output = result.get("provenance", {}).get("assessor_raw_output")
    if raw_output is not None:
        if not isinstance(raw_output, dict):
            raise ValidationError("assessor_raw_output must be a mapping")
        require_text(raw_output.get("path"), "provenance.assessor_raw_output.path")
        require_text(
            raw_output.get("content_sha256"),
            "provenance.assessor_raw_output.content_sha256",
        )
        raw_path = (TASK_ROOT / raw_output["path"]).resolve()
        raw_root = (TASK_ROOT / "outputs" / "raw").resolve()
        if not raw_path.is_relative_to(raw_root) or not raw_path.is_file():
            raise ValidationError("assessor_raw_output does not resolve under outputs/raw")
        if sha256_file(raw_path) != raw_output["content_sha256"]:
            raise ValidationError("assessor_raw_output hash mismatch")
        postprocessing = result.get("provenance", {}).get("postprocessing")
        if not isinstance(postprocessing, list) or not postprocessing:
            raise ValidationError(
                "A normalized assessor output must record postprocessing provenance"
            )

    require_text(
        result.get("assessment", {}).get("historical_scope_summary"),
        "assessment.historical_scope_summary",
    )
    expected_criteria = expected.get("criteria", [])
    criteria = result.get("criteria")
    if not isinstance(criteria, list) or len(criteria) != len(expected_criteria):
        raise ValidationError(f"Expected exactly {len(expected_criteria)} criteria")

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
            raise ValidationError(f"{prefix}.score exceeds the exceptional maximum of 4")
        if criterion["id"] in BINARY_CRITERIA and score not in {0, 3, 4}:
            raise ValidationError(f"{prefix}.score must use this rubric row's 0 or 3 anchor")
        if score == 4 and criterion["id"] != "cross_eip_interactions":
            require_text(
                criterion.get("exceptional_score_justification"),
                f"{prefix}.exceptional_score_justification",
            )
        evidence = criterion.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValidationError(f"{prefix}.evidence must contain at least one locator")
        for evidence_index, item in enumerate(evidence):
            if not isinstance(item, dict):
                raise ValidationError(f"{prefix}.evidence[{evidence_index}] must be a mapping")
            if item.get("source") not in expected_sources:
                raise ValidationError(f"{prefix}.evidence[{evidence_index}] uses a non-package source")
            require_text(item.get("locator"), f"{prefix}.evidence[{evidence_index}].locator")
            require_text(item.get("summary"), f"{prefix}.evidence[{evidence_index}].summary")
        require_text(criterion.get("rationale"), f"{prefix}.rationale")
        if criterion.get("confidence") not in CONFIDENCE:
            raise ValidationError(f"{prefix}.confidence must be low, medium, or high")
        require_text(criterion.get("uncertainty_note"), f"{prefix}.uncertainty_note")
        if criterion["id"] == "cross_eip_interactions":
            interactions = criterion.get("interacting_eips")
            if not isinstance(interactions, list):
                raise ValidationError(f"{prefix}.interacting_eips must be a list")
            unidentified = criterion.get("unidentified_interactions", [])
            if not isinstance(unidentified, list) or any(
                not isinstance(item, str) or not item.strip() for item in unidentified
            ):
                raise ValidationError(
                    f"{prefix}.unidentified_interactions must contain non-empty strings"
                )
            if score > 0 and not interactions and not unidentified:
                raise ValidationError(
                    f"{prefix} must identify or describe at least one interaction"
                )
            if score == 0 and unidentified:
                raise ValidationError(
                    f"{prefix}.unidentified_interactions must be empty for a zero score"
                )
            if any(
                not isinstance(item, int) or isinstance(item, bool) or item == number
                for item in interactions
            ):
                raise ValidationError(
                    f"{prefix}.interacting_eips must contain other EIP numbers"
                )
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
        raise ValidationError("under_specification.affected_criteria contains an invalid ID")
    plausible = under.get("plausible_total_range", {})
    minimum, maximum = plausible.get("minimum"), plausible.get("maximum")
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        raise ValidationError("plausible_total_range values must be integers")
    if minimum > total or maximum < total or minimum > maximum:
        raise ValidationError("plausible_total_range must contain the primary score")
    plausible_tiers = under.get("plausible_tiers")
    if not isinstance(plausible_tiers, list) or not plausible_tiers:
        raise ValidationError("under_specification.plausible_tiers must be non-empty")
    expected_plausible_tiers = tiers_in_range(minimum, maximum)
    if plausible_tiers != expected_plausible_tiers:
        raise ValidationError(
            f"plausible_tiers must equal {expected_plausible_tiers} for the stated range"
        )
    if not isinstance(under.get("unresolved_questions"), list):
        raise ValidationError("under_specification.unresolved_questions must be a list")

    hindsight = result.get("hindsight_control", {})
    if hindsight.get("internet_access_attempted") is not False:
        raise ValidationError("Internet access was attempted; assessment cannot be completed")
    if hindsight.get("prohibited_source_exposure") is not False:
        raise ValidationError("Prohibited source exposure prevents completion")
    if hindsight.get("contaminated") is not False:
        raise ValidationError("A contaminated assessment cannot be completed")
    if hindsight.get("exposure_details") != []:
        raise ValidationError("exposure_details must be empty for an uncontaminated run")
    require_text(hindsight.get("attestation"), "hindsight_control.attestation")
    if not isinstance(result.get("notable_ambiguities"), list):
        raise ValidationError("notable_ambiguities must be a list")
    if result.get("overall_confidence") not in CONFIDENCE:
        raise ValidationError("overall_confidence must be low, medium, or high")

    print(f"valid {fork_id} EIP-{number}: total={total} tier={expected_tier}")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fork", required=True)
    parser.add_argument("--eip", required=True, type=int)
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate(args.fork, args.eip, args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as error:
        raise SystemExit(f"validation error: {error}") from error
