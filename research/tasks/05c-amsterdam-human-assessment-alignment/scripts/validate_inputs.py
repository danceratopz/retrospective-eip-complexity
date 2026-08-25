#!/usr/bin/env python3
"""Validate source reconstruction and every blinded Task 05c package."""

from __future__ import annotations

import copy
import subprocess
from pathlib import Path
from typing import Any

from common import (
    APPROVED_ROOT,
    ASSESSOR_PROMPT_PATH,
    CONTRACT_PATH,
    EIPS_REPO,
    extract_human_scores,
    HUMAN_ROOT,
    INVENTORY_PATH,
    PACKAGE_ROOT,
    PM_REPO,
    REPO_ROOT,
    TASK05_PACKAGE_ROOT,
    TASK05_ROOT,
    StudyError,
    git_blob,
    git_commit_time,
    load_yaml,
    parse_time,
    record_payload_hash,
    rubric_semantics,
    sha256_bytes,
    sha256_file,
)


FORBIDDEN_OPERATIONAL_MARKERS = (
    "inputs/human",
    "outputs/comparisons",
    "05-retrospective-complexity-assignment/outputs/fork-eips/amsterdam",
    "checklist revision 2",
    "human score",
    "human assessment file",
    "/home/dtopz/code/github/pm",
    "/home/dtopz/code/github/retrospective-complexity-eval",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StudyError(message)


def run_task05_validators() -> None:
    python = TASK05_ROOT / ".venv/bin/python"
    result = subprocess.run(
        [str(python), str(TASK05_ROOT / "scripts/validate_inputs.py"), "--fork", "amsterdam"],
        cwd=TASK05_ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode:
        raise StudyError(f"Task 05 input validation failed:\n{result.stdout}")


def validate_human(item: dict[str, Any]) -> dict[str, Any]:
    number = int(item["eip"]["number"])
    path = REPO_ROOT / item["human_record"]["path"]
    require(sha256_file(path) == item["human_record"]["sha256"], f"EIP-{number} human record hash changed")
    record = load_yaml(path)
    payload_hash = record_payload_hash(record)
    require(
        payload_hash == record["generation"]["record_payload_sha256"],
        f"EIP-{number} human record payload hash mismatch",
    )
    event = record["human_event"]
    payload, blob = git_blob(PM_REPO, event["commit"], event["path"])
    require(blob == event["git_blob_sha"], f"EIP-{number} PM blob mismatch")
    require(sha256_bytes(payload) == event["content_sha256"], f"EIP-{number} PM content hash mismatch")
    require(
        git_commit_time(PM_REPO, event["commit"]) == event["committed_at"],
        f"EIP-{number} PM event timestamp mismatch",
    )
    rubric = record["historical_rubric"]
    rubric_payload, rubric_blob = git_blob(PM_REPO, rubric["commit"], rubric["path"])
    require(rubric_blob == rubric["git_blob_sha"], f"EIP-{number} rubric blob mismatch")
    require(sha256_bytes(rubric_payload) == rubric["content_sha256"], f"EIP-{number} rubric hash mismatch")
    require(
        git_commit_time(PM_REPO, rubric["commit"]) == rubric["committed_at"],
        f"EIP-{number} rubric timestamp mismatch",
    )
    require(
        parse_time(rubric["committed_at"]) <= parse_time(event["committed_at"]),
        f"EIP-{number} rubric postdates the human event",
    )
    semantics = rubric_semantics(rubric_payload.decode())
    require(
        [criterion["id"] for criterion in semantics["criteria"]] == rubric["anchor_order"],
        f"EIP-{number} rubric anchor order mismatch",
    )
    eip = record["human_time_eip"]
    eip_payload, eip_blob = git_blob(EIPS_REPO, eip["commit"], eip["path"])
    require(eip_blob == eip["git_blob_sha"], f"EIP-{number} human-time EIP blob mismatch")
    require(sha256_bytes(eip_payload) == eip["content_sha256"], f"EIP-{number} human-time EIP hash mismatch")
    require(
        git_commit_time(EIPS_REPO, eip["commit"]) == eip["committed_at"],
        f"EIP-{number} human-time EIP timestamp mismatch",
    )
    require(
        parse_time(eip["committed_at"]) <= parse_time(event["committed_at"]),
        f"EIP-{number} human-time EIP postdates the human event",
    )
    require(record["numeric_total_unambiguous"], f"EIP-{number} human total remains ambiguous")
    reconstructed = extract_human_scores(payload.decode(), rubric_semantics(payload.decode()))
    for field in (
        "scores",
        "published_total",
        "published_tier_raw",
        "published_tier",
        "recomputed_total",
        "recomputed_tier",
        "numeric_total_unambiguous",
        "parser_notes",
    ):
        require(
            record[field] == reconstructed[field],
            f"EIP-{number} reconstructed human field differs: {field}",
        )
    require(
        record["published_total"] == record["recomputed_total"],
        f"EIP-{number} published/recomputed human total mismatch",
    )
    require(
        record["published_tier"] == record["recomputed_tier"],
        f"EIP-{number} published/recomputed human tier mismatch",
    )
    return record


def validate_package(item: dict[str, Any], human: dict[str, Any]) -> None:
    number = int(item["eip"]["number"])
    package = PACKAGE_ROOT / f"eip-{number}"
    manifest_path = package / "manifest.yaml"
    template_path = package / "output-template.yaml"
    manifest = load_yaml(manifest_path)
    template = load_yaml(template_path)
    source_package = TASK05_PACKAGE_ROOT / f"eip-{number}"
    source_manifest_path = source_package / "manifest.yaml"
    source_manifest = load_yaml(source_manifest_path)

    require(manifest["eip"] == item["eip"], f"EIP-{number} package identity mismatch")
    require(
        sha256_file(source_manifest_path) == item["task_05_package_manifest"]["sha256"],
        f"EIP-{number} Task 05 package changed after discovery",
    )
    source_output = REPO_ROOT / item["task_05_output"]["path"]
    require(
        sha256_file(source_output) == item["task_05_output"]["sha256"],
        f"EIP-{number} Task 05 output changed after discovery",
    )
    require(
        manifest["historical_eip"] == source_manifest["historical_eip"],
        f"EIP-{number} historical EIP provenance differs from Task 05",
    )
    require(
        manifest["supporting_documents"] == source_manifest["supporting_documents"],
        f"EIP-{number} supporting allowlist differs from Task 05",
    )
    require(
        manifest["provenance_only_links"] == source_manifest["provenance_only_links"],
        f"EIP-{number} provenance-only links differ from Task 05",
    )
    require(
        manifest["assessment_source_files"] == source_manifest["assessment_source_files"],
        f"EIP-{number} assessment source file order differs from Task 05",
    )
    for name in source_manifest["assessment_source_files"]:
        if name == "rubric.md":
            require(
                sha256_file(package / name) == human["historical_rubric"]["content_sha256"],
                f"EIP-{number} historical rubric package hash mismatch",
            )
        else:
            require(
                (package / name).read_bytes() == (source_package / name).read_bytes(),
                f"EIP-{number} Task 05 source blob differs: {name}",
            )
    package_files = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    }
    expected_files = {
        "manifest.yaml",
        "output-template.yaml",
        *source_manifest["assessment_source_files"],
    }
    require(package_files == expected_files, f"EIP-{number} package contains unexpected files: {package_files - expected_files}")
    require(
        template["provenance"]["input_package"]["manifest_sha256"] == sha256_file(manifest_path),
        f"EIP-{number} output template manifest hash mismatch",
    )
    expected_ids = human["historical_rubric"]["anchor_order"]
    require(
        [criterion["id"] for criterion in template["criteria"]] == expected_ids,
        f"EIP-{number} output template anchor order mismatch",
    )
    require(len(template["criteria"]) == 24, f"EIP-{number} historical template must have 24 rows")
    require(template["totals"]["maximum_score"] == 72, f"EIP-{number} historical maximum must be 72")

    operational_text = "\n".join(
        [
            manifest_path.read_text(encoding="utf-8"),
            template_path.read_text(encoding="utf-8"),
            ASSESSOR_PROMPT_PATH.read_text(encoding="utf-8"),
            CONTRACT_PATH.read_text(encoding="utf-8"),
        ]
    ).lower()
    for marker in FORBIDDEN_OPERATIONAL_MARKERS:
        require(marker.lower() not in operational_text, f"EIP-{number} operational material exposes forbidden marker: {marker}")


def main() -> int:
    run_task05_validators()
    inventory = load_yaml(INVENTORY_PATH)
    approved = {
        int(path.stem.removeprefix("eip-"))
        for path in APPROVED_ROOT.glob("eip-*.yaml")
        if load_yaml(path).get("review", {}).get("status") == "approved"
    }
    inventory_numbers = {int(item["eip"]["number"]) for item in inventory["eips"]}
    require(inventory_numbers == approved, "Study inventory does not exhaust approved Amsterdam Task 04 refs")
    exclusions = [item for item in inventory["eips"] if item["status"] == "excluded"]
    for item in exclusions:
        require(bool(item["exclusion_reasons"]), f"EIP-{item['eip']['number']} exclusion has no reason")
    included = [item for item in inventory["eips"] if item["status"] == "included"]
    require(len(included) + len(exclusions) == len(approved), "Inclusion/exclusion counts do not exhaust inventory")
    for item in included:
        number = int(item["eip"]["number"])
        ref_path = REPO_ROOT / item["task_04_ref"]["path"]
        require(sha256_file(ref_path) == item["task_04_ref"]["sha256"], f"EIP-{number} Task 04 ref changed")
        human = validate_human(item)
        validate_package(item, human)
        print(
            f"valid input EIP-{number}: human={human['recomputed_total']} "
            f"rubric={human['historical_rubric']['commit'][:12]} "
            f"alignment={human['input_alignment']['classification']}"
        )
    print(f"valid study inputs: included={len(included)} excluded={len(exclusions)} approved={len(approved)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StudyError as error:
        raise SystemExit(f"input validation error: {error}") from error
