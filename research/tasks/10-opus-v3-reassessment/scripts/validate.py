#!/usr/bin/env python3
"""Validate Task 10 assessments with the Task 05 validator's helpers and the v3 pins.

    validate.py                       # every package that has an assessment; fails on missing ones with --complete
    validate.py --only shanghai/3855 hegota/8141
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import common
from common import TASK_ID, XEIP, load_yaml
from engine_adapter import TASK_ROOT, output_engine, package_engine


CONFIDENCE = output_engine.CONFIDENCE
BINARY_CRITERIA = output_engine.BINARY_CRITERIA
require_text = output_engine.require_text
tier = output_engine.tier
tiers_in_range = output_engine.tiers_in_range
sha256_file = package_engine.file_sha256


class ValidationError(RuntimeError):
    """Raised when an assessment violates the Task 10 contract."""


def cases() -> list[dict[str, Any]]:
    """Every Task 10 package with its output, raw and failure paths."""
    found = []
    for mode, tree in (("retrospective", "retrospective"), ("prospective", "prospective")):
        for manifest_path in sorted((TASK_ROOT / tree / "inputs" / "packages").glob("*/eip-*/manifest.yaml")):
            package = manifest_path.parent
            group = package.parent.name
            number = int(package.name.removeprefix("eip-"))
            outputs = TASK_ROOT / tree / "outputs"
            fork = "hegota" if mode == "prospective" else group
            found.append(
                {
                    "key": f"{fork}/{number}",
                    "mode": mode,
                    "fork": fork,
                    "number": number,
                    "package": package,
                    "output": outputs / "assessments" / group / f"eip-{number}.yaml",
                    "raw": outputs / "raw" / group / f"eip-{number}.json",
                    "failed": outputs / "failed" / group,
                }
            )
    return found


def validate(case: dict[str, Any]) -> tuple[int, str]:
    package, number, mode = case["package"], case["number"], case["mode"]
    manifest = load_yaml(package / "manifest.yaml")
    expected = load_yaml(package / "output-template.yaml")
    result = load_yaml(case["output"])
    _, rubric_manifest = common.frozen_rubric()
    rubric = rubric_manifest["parsed"]
    config = common.config()

    if result.get("schema_version") != 1 or result.get("task_id") != TASK_ID:
        raise ValidationError("Unexpected schema_version or task_id")
    if result.get("fork_id") != case["fork"] or int(result.get("eip", {}).get("number", -1)) != number:
        raise ValidationError("Fork or EIP identity mismatch")
    if result.get("eip") != expected["eip"]:
        raise ValidationError("EIP identity fields differ from the sealed template")
    if mode == "prospective":
        for key in ("snapshot_id", "eip_8081_list"):
            if result.get(key) != expected[key]:
                raise ValidationError(f"{key} differs from the sealed template")
        if "historical_scope_summary" in result.get("assessment", {}) or "hindsight_control" in result:
            raise ValidationError("Prospective records must not persist historical fields")
        scope_field, control_key = "snapshot_scope_summary", "information_control"
        flags = ("internet_access_attempted", "post_snapshot_information_exposure", "prohibited_source_exposure", "contaminated")
    else:
        scope_field, control_key = "historical_scope_summary", "hindsight_control"
        flags = ("internet_access_attempted", "prohibited_source_exposure", "contaminated")

    immutable = [key for key in expected["provenance"] if key not in {"assessor"}]
    for field in immutable:
        if result.get("provenance", {}).get(field) != expected["provenance"][field]:
            raise ValidationError(f"Immutable provenance changed: provenance.{field}")
    if expected["provenance"]["input_package"]["manifest_sha256"] != sha256_file(package / "manifest.yaml"):
        raise ValidationError("Package manifest hash no longer matches the template")
    for key in ("task_contract", "system_prompt", "session_prompt"):
        item = expected["provenance"][key]
        if sha256_file(common.REPO_ROOT / item["path"]) != item["content_sha256"]:
            raise ValidationError(f"{key} hash no longer matches the template")
    if mode == "retrospective":
        source = expected["provenance"]["source_package"]
        if sha256_file(common.REPO_ROOT / source["manifest_path"]) != source["manifest_sha256"]:
            raise ValidationError("Task 05 source package manifest changed")
    for item in manifest["materialized_files"]:
        if sha256_file(package / item["path"]) != item["content_sha256"]:
            raise ValidationError(f"Package file changed: {item['path']}")

    assessor = result["provenance"]["assessor"]
    runtime = config["runtime"]
    if assessor.get("model") != runtime["model"] or assessor.get("reasoning_effort") != runtime["effort"]:
        raise ValidationError(f"Assessor must be {runtime['model']} at {runtime['effort']}")
    for field in ("run_at", "session_id", "session_id_source", "isolation_method", "agent_identity"):
        require_text(assessor.get(field), f"provenance.assessor.{field}")
    if assessor["session_id_source"] != "isolated_launcher_run_id" or not assessor["session_id"].startswith(
        "assessment-run-"
    ):
        raise ValidationError("session_id must be populated by the isolated launcher")
    if assessor["isolation_method"] != common.ISOLATION_METHOD:
        raise ValidationError("Unexpected isolation method")
    if assessor.get("skills_used") != [] or assessor.get("prohibited_skill_exposure") is not False:
        raise ValidationError("Skills must not be exposed or used")

    engine = result["provenance"].get("engine", {})
    if engine.get("model") != runtime["model"] or engine.get("effort") != runtime["effort"]:
        raise ValidationError("Engine model or effort differs from config")
    if engine.get("claude_flags") != runtime["claude_flags"]:
        raise ValidationError("Engine flags differ from config")
    if engine.get("advisor_model") is not None or engine.get("fallback_model") is not None:
        raise ValidationError("No advisor or fallback model is permitted")
    request = manifest["request"]
    if engine.get("prompt_sha256") != request["prompt_sha256"]:
        raise ValidationError("Response prompt hash differs from the package request")
    if engine.get("system_prompt_sha256") != request["system_prompt_sha256"]:
        raise ValidationError("Response system-prompt hash differs from the package request")
    if engine.get("schema_sha256") != request["schema"]["content_sha256"]:
        raise ValidationError("Response schema hash differs from the package request")
    require_text(engine.get("claude_code_version"), "provenance.engine.claude_code_version")
    if not isinstance(engine.get("total_cost_usd"), (int, float)) or not isinstance(engine.get("usage"), dict):
        raise ValidationError("Engine usage and cost report missing")

    raw_output = result["provenance"].get("assessor_raw_output")
    if not isinstance(raw_output, dict):
        raise ValidationError("assessor_raw_output is required")
    raw_path = (TASK_ROOT / raw_output["path"]).resolve()
    if raw_path != case["raw"].resolve() or not raw_path.is_file():
        raise ValidationError("assessor_raw_output does not resolve to this case's raw response")
    if sha256_file(raw_path) != raw_output["content_sha256"]:
        raise ValidationError("assessor_raw_output hash mismatch")
    if not isinstance(result["provenance"].get("postprocessing"), list) or not result["provenance"]["postprocessing"]:
        raise ValidationError("postprocessing provenance is required")

    sources = manifest["assessment_source_files"]
    if result["provenance"].get("sources_consulted") != sources:
        raise ValidationError("sources_consulted differs from the sealed allowlist")
    require_text(result.get("assessment", {}).get(scope_field), f"assessment.{scope_field}")

    expected_criteria = expected["criteria"]
    criteria = result.get("criteria")
    if not isinstance(criteria, list) or len(criteria) != 28 or len(expected_criteria) != 28:
        raise ValidationError("Expected exactly 28 criteria")
    candidates = request["candidate_interacting_eips"]
    total = 0
    for index, (criterion, expected_criterion) in enumerate(zip(criteria, expected_criteria)):
        prefix = f"criteria[{index}]"
        if criterion.get("id") != expected_criterion["id"] or criterion.get("label") != expected_criterion["label"]:
            raise ValidationError(f"{prefix} is out of canonical order or relabelled")
        score = criterion.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or score < 0:
            raise ValidationError(f"{prefix}.score must be a non-negative integer")
        level = criterion["base_score"] if criterion["id"] == XEIP else score
        if level not in common.permitted_levels(rubric, criterion["id"]):
            raise ValidationError(f"{prefix} level {level} is not permitted by the v3 rubric")
        if criterion["id"] in BINARY_CRITERIA and level not in {0, 3, 4}:
            raise ValidationError(f"{prefix} violates the binary rubric anchors")
        if level == 4:
            require_text(criterion.get("exceptional_score_justification"), f"{prefix}.exceptional_score_justification")
        evidence = criterion.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ValidationError(f"{prefix}.evidence must contain at least one locator")
        for position, item in enumerate(evidence):
            if not isinstance(item, dict) or item.get("source") not in sources:
                raise ValidationError(f"{prefix}.evidence[{position}] uses a non-package source")
            require_text(item.get("locator"), f"{prefix}.evidence[{position}].locator")
            require_text(item.get("summary"), f"{prefix}.evidence[{position}].summary")
        require_text(criterion.get("rationale"), f"{prefix}.rationale")
        if criterion.get("confidence") not in CONFIDENCE:
            raise ValidationError(f"{prefix}.confidence is invalid")
        require_text(criterion.get("uncertainty_note"), f"{prefix}.uncertainty_note")
        if criterion["id"] == XEIP:
            interactions = criterion.get("interacting_eips")
            details = criterion.get("interaction_details")
            unidentified = criterion.get("unidentified_interactions")
            if not isinstance(interactions, list) or not isinstance(details, list) or not isinstance(unidentified, list):
                raise ValidationError(f"{prefix} interaction fields must be lists")
            if interactions != [item["eip"] for item in details] or len(set(interactions)) != len(interactions):
                raise ValidationError(f"{prefix}.interacting_eips must list each detailed EIP once")
            if any(item not in candidates or item == number for item in interactions):
                raise ValidationError(f"{prefix}.interacting_eips contains a non-candidate EIP")
            qualifying = [item["eip"] for item in details if item["interaction"] == "coordinated_cases"]
            if criterion.get("bonus_qualifying_eips") != qualifying:
                raise ValidationError(f"{prefix}.bonus_qualifying_eips differs from the coordinated-case EIPs")
            if criterion.get("bonus") != common.cross_eip_bonus(rubric, len(qualifying)):
                raise ValidationError(f"{prefix}.bonus differs from the rubric's increment rule")
            if score != criterion["base_score"] + criterion["bonus"]:
                raise ValidationError(f"{prefix}.score must equal base_score + bonus")
            if criterion["base_score"] == 0 and unidentified:
                raise ValidationError(f"{prefix} has unidentified interactions at level zero")
        total += score

    totals = result.get("totals", {})
    if totals.get("primary_score") != total:
        raise ValidationError(f"primary_score must equal criterion sum {total}")
    if totals.get("complexity_tier") != tier(total):
        raise ValidationError(f"complexity_tier must be {tier(total)}")

    under = result.get("under_specification", {})
    if not isinstance(under.get("present"), bool):
        raise ValidationError("under_specification.present must be boolean")
    require_text(under.get("summary"), "under_specification.summary")
    valid_ids = [item["id"] for item in expected_criteria]
    affected = under.get("affected_criteria")
    if not isinstance(affected, list) or not set(affected).issubset(valid_ids):
        raise ValidationError("under_specification.affected_criteria is invalid")
    if [item["criterion"] for item in under.get("criterion_ranges", [])] != affected:
        raise ValidationError("criterion_ranges must follow affected_criteria")
    by_id = {item["id"]: item for item in criteria}
    low = high = total
    for item in under["criterion_ranges"]:
        criterion = by_id[item["criterion"]]
        level = criterion["base_score"] if item["criterion"] == XEIP else criterion["score"]
        if not item["minimum_score"] <= level <= item["maximum_score"]:
            raise ValidationError(f"{item['criterion']} range must contain its level")
        low += item["minimum_score"] - level
        high += item["maximum_score"] - level
    plausible = under.get("plausible_total_range", {})
    if plausible != {"minimum": max(0, low), "maximum": high}:
        raise ValidationError("plausible_total_range must follow from the criterion ranges")
    if under.get("plausible_tiers") != tiers_in_range(plausible["minimum"], plausible["maximum"]):
        raise ValidationError("plausible_tiers does not match the stated range")
    if not isinstance(under.get("unresolved_questions"), list):
        raise ValidationError("under_specification.unresolved_questions must be a list")

    control = result.get(control_key, {})
    for flag in flags:
        if control.get(flag) is not False:
            raise ValidationError(f"{control_key}.{flag} prevents completion")
    if control.get("exposure_details") != []:
        raise ValidationError("exposure_details must be empty")
    require_text(control.get("attestation"), f"{control_key}.attestation")
    if not isinstance(result.get("notable_ambiguities"), list):
        raise ValidationError("notable_ambiguities must be a list")
    if result.get("overall_confidence") not in CONFIDENCE:
        raise ValidationError("overall_confidence is invalid")
    return total, tier(total)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="fork/eip keys, for example shanghai/3855 hegota/8141")
    parser.add_argument("--complete", action="store_true", help="Fail when any package lacks an assessment")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = [case for case in cases() if not args.only or case["key"] in args.only]
    missing, errors = [], []
    for case in selected:
        if not case["output"].is_file():
            missing.append(case["key"])
            continue
        try:
            total, level = validate(case)
            print(f"valid {case['key']}: total={total} tier={level}")
        except (ValidationError, output_engine.ValidationError, KeyError, TypeError) as error:
            errors.append(f"{case['key']}: {error}")
    for error in errors:
        print(f"INVALID {error}")
    print(f"{len(selected) - len(missing) - len(errors)} valid, {len(errors)} invalid, {len(missing)} missing")
    return 1 if errors or (args.complete and missing) else 0


if __name__ == "__main__":
    raise SystemExit(main())
