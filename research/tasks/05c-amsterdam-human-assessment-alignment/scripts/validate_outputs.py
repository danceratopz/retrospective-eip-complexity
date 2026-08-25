#!/usr/bin/env python3
"""Validate historical-checklist outputs and the immutable automated freeze."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from common import (
    AUTOMATED_ROOT,
    CONFIDENCE,
    FREEZE_PATH,
    INVENTORY_PATH,
    PACKAGE_ROOT,
    REPO_ROOT,
    TASK_ROOT,
    StudyError,
    aggregate_hash,
    load_yaml,
    parse_time,
    rel,
    sha256_file,
    tier,
    tiers_in_range,
    yaml_bytes,
    write_bytes,
)


ISOLATION_METHOD = "bubblewrap_one_eip_capsule_v1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StudyError(message)


def require_text(value: Any, field: str) -> None:
    require(isinstance(value, str) and bool(value.strip()), f"{field} must be a non-empty string")


def validate_automated(number: int, output_override: Path | None = None) -> Path:
    package = PACKAGE_ROOT / f"eip-{number}"
    manifest_path = package / "manifest.yaml"
    template_path = package / "output-template.yaml"
    output_path = output_override or AUTOMATED_ROOT / f"eip-{number}.yaml"
    require(output_path.is_file(), f"Missing automated output: {output_path}")
    manifest = load_yaml(manifest_path)
    expected = load_yaml(template_path)
    result = load_yaml(output_path)
    require(result.get("schema_version") == 1, f"EIP-{number} output schema mismatch")
    require(result.get("task_id") == expected["task_id"], f"EIP-{number} task identity mismatch")
    require(result.get("fork_id") == "amsterdam", f"EIP-{number} fork mismatch")
    require(result.get("eip") == expected["eip"], f"EIP-{number} identity fields changed")

    provenance = result.get("provenance", {})
    expected_provenance = expected["provenance"]
    for field in (
        "input_package",
        "historical_eip",
        "historical_rubric",
        "task_contract",
        "assessor_prompt",
        "sources_consulted",
        "operational_files_read",
    ):
        require(
            provenance.get(field) == expected_provenance[field],
            f"EIP-{number} immutable provenance changed: {field}",
        )
    require(
        provenance["input_package"]["manifest_sha256"] == sha256_file(manifest_path),
        f"EIP-{number} manifest hash is stale",
    )
    environment = provenance.get("assessor_environment", {})
    require(environment.get("model") == "gpt-5.6-sol", f"EIP-{number} model mismatch")
    require(environment.get("reasoning_effort") == "xhigh", f"EIP-{number} effort mismatch")
    require(environment.get("approval_policy") == "never", f"EIP-{number} approval policy mismatch")
    require(environment.get("codex_executable_path") == "/home/dtopz/.local/bin/codex", f"EIP-{number} Codex path mismatch")
    require_text(environment.get("codex_version"), f"EIP-{number} codex_version")
    require(
        isinstance(environment.get("codex_binary_sha256"), str)
        and bool(re.fullmatch(r"[0-9a-f]{64}", environment["codex_binary_sha256"])),
        f"EIP-{number} Codex binary hash invalid",
    )
    require(
        isinstance(environment.get("command"), list)
        and environment["command"]
        and all(isinstance(item, str) and item for item in environment["command"]),
        f"EIP-{number} command provenance invalid",
    )
    for field in ("run_at", "session_id", "session_id_source", "isolation_method", "agent_identity"):
        require_text(environment.get(field), f"EIP-{number} assessor_environment.{field}")
    require(environment["session_id"].startswith("assessment-run-"), f"EIP-{number} session ID is not launcher-owned")
    require(environment["session_id_source"] == "isolated_launcher_run_id", f"EIP-{number} session source mismatch")
    require(environment["isolation_method"] == ISOLATION_METHOD, f"EIP-{number} isolation method mismatch")
    require(environment.get("skills_used") == [], f"EIP-{number} prohibited skill use recorded")
    require(environment.get("prohibited_capability_exposure") is False, f"EIP-{number} prohibited capability exposure")
    launcher_path = REPO_ROOT / environment["launcher_path"]
    require(sha256_file(launcher_path) == environment["launcher_sha256"], f"EIP-{number} launcher hash is stale")

    expected_criteria = expected["criteria"]
    criteria = result.get("criteria")
    require(isinstance(criteria, list) and len(criteria) == len(expected_criteria), f"EIP-{number} criterion count mismatch")
    total = 0
    source_allowlist = manifest["assessment_source_files"]
    for index, (criterion, expected_criterion) in enumerate(zip(criteria, expected_criteria)):
        prefix = f"EIP-{number} criteria[{index}]"
        for field in ("id", "label", "definition_present", "allowed_scores"):
            require(criterion.get(field) == expected_criterion[field], f"{prefix}.{field} changed")
        score = criterion.get("score")
        require(type(score) is int and score in criterion["allowed_scores"], f"{prefix}.score not allowed")
        if score == 4:
            require_text(criterion.get("exceptional_score_justification"), f"{prefix}.exceptional_score_justification")
        evidence = criterion.get("evidence")
        require(isinstance(evidence, list) and evidence, f"{prefix}.evidence must be non-empty")
        for evidence_index, item in enumerate(evidence):
            require(isinstance(item, dict), f"{prefix}.evidence[{evidence_index}] must be a mapping")
            require(item.get("source") in source_allowlist, f"{prefix}.evidence[{evidence_index}] uses forbidden source")
            require_text(item.get("locator"), f"{prefix}.evidence[{evidence_index}].locator")
            require_text(item.get("summary"), f"{prefix}.evidence[{evidence_index}].summary")
        require_text(criterion.get("rationale"), f"{prefix}.rationale")
        require(criterion.get("confidence") in CONFIDENCE, f"{prefix}.confidence invalid")
        require_text(criterion.get("uncertainty_note"), f"{prefix}.uncertainty_note")
        if criterion["id"] == "engine_api_encoding_changes":
            require(
                "definition" in criterion["uncertainty_note"].lower(),
                f"{prefix} must acknowledge the historical source's missing definition",
            )
        total += score

    totals = result.get("totals", {})
    require(totals.get("primary_score") == total, f"EIP-{number} total must equal {total}")
    require(totals.get("maximum_score") == 72, f"EIP-{number} nominal maximum mismatch")
    require(totals.get("complexity_tier") == tier(total), f"EIP-{number} tier mismatch")
    require(totals.get("tier_thresholds") == expected["totals"]["tier_thresholds"], f"EIP-{number} thresholds changed")
    under = result.get("under_specification", {})
    require(type(under.get("present")) is bool, f"EIP-{number} under_specification.present invalid")
    require_text(under.get("summary"), f"EIP-{number} under_specification.summary")
    valid_ids = {item["id"] for item in expected_criteria}
    affected = under.get("affected_criteria")
    require(isinstance(affected, list) and set(affected).issubset(valid_ids), f"EIP-{number} affected criteria invalid")
    plausible = under.get("plausible_total_range", {})
    minimum, maximum = plausible.get("minimum"), plausible.get("maximum")
    require(type(minimum) is int and type(maximum) is int, f"EIP-{number} plausible range invalid")
    require(minimum <= total <= maximum, f"EIP-{number} plausible range does not contain total")
    require(under.get("plausible_tiers") == tiers_in_range(minimum, maximum), f"EIP-{number} plausible tiers mismatch")
    require(isinstance(under.get("unresolved_questions"), list), f"EIP-{number} unresolved questions invalid")
    hindsight = result.get("hindsight_control", {})
    require(hindsight.get("internet_access_attempted") is False, f"EIP-{number} internet access attempted")
    require(hindsight.get("prohibited_source_exposure") is False, f"EIP-{number} prohibited source exposure")
    require(hindsight.get("contaminated") is False, f"EIP-{number} contaminated")
    require(hindsight.get("exposure_details") == [], f"EIP-{number} exposure details must be empty")
    require_text(hindsight.get("package_grounding_attestation"), f"EIP-{number} package grounding attestation")
    latent_acknowledgement = hindsight.get("latent_knowledge_limitation_acknowledged")
    require(
        latent_acknowledgement is True
        or (isinstance(latent_acknowledgement, str) and bool(latent_acknowledgement.strip())),
        f"EIP-{number} latent knowledge limitation not acknowledged",
    )
    require(isinstance(result.get("notable_ambiguities"), list), f"EIP-{number} notable ambiguities invalid")
    require(result.get("overall_confidence") in CONFIDENCE, f"EIP-{number} overall confidence invalid")
    return output_path


def freeze_data() -> dict[str, Any]:
    inventory = load_yaml(INVENTORY_PATH)
    included = [item for item in inventory["eips"] if item["status"] == "included"]
    entries: list[dict[str, Any]] = []
    sessions: set[str] = set()
    run_times: list[Any] = []
    for item in included:
        number = int(item["eip"]["number"])
        output = validate_automated(number)
        result = load_yaml(output)
        session = result["provenance"]["assessor_environment"]["session_id"]
        require(session not in sessions, f"Automated session ID reused: {session}")
        sessions.add(session)
        run_at = result["provenance"]["assessor_environment"]["run_at"]
        run_times.append(parse_time(run_at))
        package = PACKAGE_ROOT / f"eip-{number}"
        package_hash, package_files = aggregate_hash(
            [path for path in package.rglob("*") if path.is_file()], package
        )
        entries.append(
            {
                "eip": number,
                "package_path": rel(package),
                "package_sha256": package_hash,
                "package_files": package_files,
                "automated_output_path": rel(output),
                "automated_output_sha256": sha256_file(output),
                "session_id": session,
                "run_at": run_at,
                "model": "gpt-5.6-sol",
                "reasoning_effort": "xhigh",
            }
        )
    frozen_at = max(run_times).isoformat().replace("+00:00", "Z") if run_times else None
    return {
        "schema_version": 1,
        "task_id": "05c-amsterdam-human-assessment-alignment-automated-freeze",
        "freeze_policy": "deterministic_manifest_of_validated_non_overwriting_automated_outputs",
        "frozen_at": frozen_at,
        "study_inventory": {"path": rel(INVENTORY_PATH), "sha256": sha256_file(INVENTORY_PATH)},
        "generation_script": {"path": rel(Path(__file__)), "sha256": sha256_file(Path(__file__))},
        "outputs": entries,
    }


def create_freeze() -> None:
    payload = yaml_bytes(freeze_data())
    if FREEZE_PATH.exists() and FREEZE_PATH.read_bytes() != payload:
        raise StudyError(f"Existing freeze is stale and would be overwritten: {FREEZE_PATH}")
    write_bytes(FREEZE_PATH, payload, overwrite=False)
    require(FREEZE_PATH.read_bytes() == yaml_bytes(freeze_data()), "Freeze regeneration is not byte-identical")


def validate_freeze() -> dict[str, Any]:
    require(FREEZE_PATH.is_file(), "Automated freeze manifest is missing")
    expected = yaml_bytes(freeze_data())
    require(FREEZE_PATH.read_bytes() == expected, "Automated freeze manifest is stale or inconsistent")
    return load_yaml(FREEZE_PATH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eip", type=int)
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--validate-freeze", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.eip is not None:
        path = validate_automated(args.eip, args.output)
        result = load_yaml(path)
        print(f"valid automated EIP-{args.eip}: total={result['totals']['primary_score']} tier={result['totals']['complexity_tier']}")
        return 0
    if args.freeze:
        create_freeze()
        print(f"created and byte-verified automated freeze: {FREEZE_PATH}")
        return 0
    if args.validate_freeze:
        freeze = validate_freeze()
        print(f"valid automated freeze: outputs={len(freeze['outputs'])}")
        return 0
    inventory = load_yaml(INVENTORY_PATH)
    included = [item for item in inventory["eips"] if item["status"] == "included"]
    for item in included:
        validate_automated(int(item["eip"]["number"]))
    print(f"valid automated outputs: {len(included)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StudyError as error:
        raise SystemExit(f"output validation error: {error}") from error
