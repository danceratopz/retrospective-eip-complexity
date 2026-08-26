#!/usr/bin/env python3
"""Validate sealed Task 08 packages and their approved inventory."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from engine_adapter import REPO_ROOT, TASK05_ROOT, TASK_ROOT, package_engine


NAMESPACE = "hegota-pfi-2026-08-26"
PACKAGE_ROOT = TASK_ROOT / "inputs" / "packages" / NAMESPACE
PROMPT_ROOT = TASK_ROOT / "inputs" / "prompts" / NAMESPACE
COHORT_PATH = TASK_ROOT / "inputs" / "hegota-pfi-2026-08-26.yaml"
REVIEW_PATH = TASK_ROOT / "outputs" / "cohort-review.yaml"
TASK_CONTRACT = TASK_ROOT / "TASK.md"
ASSESSMENT_CONTRACT = TASK_ROOT / "prompts" / "ASSESSMENT-CONTRACT.md"
TASK05_TEMPLATE = TASK05_ROOT / "templates" / "output.yaml"
PACKAGE_FREEZE = TASK_ROOT / "outputs" / "package-manifest.yaml"
PROVENANCE_ONLY_REPOSITORIES = {
    *package_engine.PROVENANCE_ONLY_REPOSITORIES,
    "ethereum/consensus-specs",
}

load_yaml = package_engine.load_yaml
file_sha256 = package_engine.file_sha256


class ValidationError(RuntimeError):
    """Raised when a Task 08 sealed package is inconsistent."""


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def expected_entries() -> list[dict[str, Any]]:
    cohort = load_yaml(COHORT_PATH)
    review = load_yaml(REVIEW_PATH)
    if review.get("review_gate", {}).get("status") != "approved":
        raise ValidationError("Cohort review is not approved")
    entries = review.get("entries", [])
    if [item.get("eip") for item in entries] != [
        item.get("eip") for item in cohort.get("inventory", [])
    ]:
        raise ValidationError("Cohort review does not preserve source order")
    if not all(item.get("review", {}).get("status") == "approved" for item in entries):
        raise ValidationError("Every cohort entry must be approved")
    return [item for item in entries if item.get("disposition") == "score_el_rubric"]


def validate_package(package: Path) -> None:
    manifest_path = package / "manifest.yaml"
    template_path = package / "output-template.yaml"
    manifest = load_yaml(manifest_path)
    template = load_yaml(template_path)
    number = int(manifest.get("eip", {}).get("number", -1))
    identity = (
        manifest.get("task_id"),
        manifest.get("fork_id"),
        manifest.get("snapshot_id"),
        package.name,
    )
    if identity != (
        "08-hegota-prospective-complexity-assessment",
        "hegota",
        "hegota-pfi-2026-08-26-ac450a4",
        f"eip-{number}",
    ):
        raise ValidationError(f"Package identity mismatch: {package}")

    review = load_yaml(REVIEW_PATH)
    matching = [item for item in review["entries"] if int(item["eip"]) == number]
    if len(matching) != 1:
        raise ValidationError(f"EIP-{number} lacks one cohort-review entry")
    entry = matching[0]
    if entry["disposition"] != "score_el_rubric" or entry["review"]["status"] != "approved":
        raise ValidationError(f"EIP-{number} is not approved for the EL rubric")
    if manifest["eip"] != {
        "number": number,
        "title": entry["canonical_title"],
        "layers": entry["affected_layers"],
    }:
        raise ValidationError(f"EIP-{number} identity differs from the cohort review")
    if manifest.get("cohort_manifest") != {
        "path": rel(COHORT_PATH),
        "content_sha256": file_sha256(COHORT_PATH),
        "snapshot_id": "hegota-pfi-2026-08-26-ac450a4",
    }:
        raise ValidationError(f"EIP-{number} cohort-manifest provenance mismatch")
    review_record = manifest.get("cohort_review", {})
    if (
        review_record.get("path") != rel(REVIEW_PATH)
        or review_record.get("content_sha256") != file_sha256(REVIEW_PATH)
        or review_record.get("review_status") != "approved"
        or review_record.get("disposition") != "score_el_rubric"
        or review_record.get("affected_layers") != entry["affected_layers"]
    ):
        raise ValidationError(f"EIP-{number} cohort-review provenance mismatch")

    expected_sources = ["eip.md", "rubric.md"]
    expected_files = {"manifest.yaml", "output-template.yaml", "eip.md", "rubric.md"}
    primary = manifest.get("snapshot_eip", {})
    eip_path = package / primary.get("package_path", "")
    if not eip_path.is_file() or file_sha256(eip_path) != primary.get("content_sha256"):
        raise ValidationError(f"EIP-{number} primary EIP hash mismatch")
    if primary.get("commit") != "ac450a4ab2f37387385ee9c54b62f518d97e6cc9":
        raise ValidationError(f"EIP-{number} uses the wrong common snapshot")
    rubric = manifest.get("rubric", {})
    rubric_path = package / rubric.get("package_path", "")
    if not rubric_path.is_file() or file_sha256(rubric_path) != rubric.get(
        "assessor_view_sha256"
    ):
        raise ValidationError(f"EIP-{number} rubric hash mismatch")
    task05_view = TASK05_ROOT / "inputs" / "rubric" / "assessor-view.md"
    if rubric_path.read_bytes() != task05_view.read_bytes():
        raise ValidationError(f"EIP-{number} rubric differs from Task 05")
    rubric_text = rubric_path.read_text(encoding="utf-8")
    if "Amsterdam calibration" in rubric_text or "##### Revision Notes" in rubric_text:
        raise ValidationError(f"EIP-{number} exposes retrospective rubric notes")

    for supporting in manifest.get("supporting_documents", []):
        if supporting.get("repository") in package_engine.PROVENANCE_ONLY_REPOSITORIES:
            raise ValidationError(f"EIP-{number} packages prohibited repository evidence")
        relative = supporting.get("package_path")
        path = package / relative
        if not path.is_file() or file_sha256(path) != supporting.get("content_sha256"):
            raise ValidationError(f"EIP-{number} supporting hash mismatch: {relative}")
        expected_sources.append(relative)
        expected_files.add(relative)
    if manifest.get("assessment_source_files") != expected_sources:
        raise ValidationError(f"EIP-{number} assessment source order mismatch")
    for link in manifest.get("provenance_only_links", []):
        if (
            link.get("repository") not in PROVENANCE_ONLY_REPOSITORIES
            or link.get("use") != "provenance_only"
            or "package_path" in link
        ):
            raise ValidationError(f"EIP-{number} invalid provenance-only link")
    policy = manifest.get("source_policy", {})
    for field in (
        "internet_allowed",
        "follow_links_allowed",
        "files_outside_package_allowed",
        "dedicated_assessment_skill_allowed",
        "opportunistic_repository_evidence_allowed",
        "post_snapshot_information_allowed",
    ):
        if policy.get(field) is not False:
            raise ValidationError(f"EIP-{number} source policy permits {field}")
    if policy.get("provenance_only_repositories") != sorted(
        PROVENANCE_ONLY_REPOSITORIES
    ):
        raise ValidationError(f"EIP-{number} provenance-only repository policy mismatch")

    materialized = manifest.get("materialized_files")
    expected_materialized = ["eip.md", "rubric.md", *expected_sources[2:]]
    if [item.get("path") for item in materialized] != expected_materialized:
        raise ValidationError(f"EIP-{number} materialized-file inventory mismatch")
    for item in materialized:
        if file_sha256(package / item["path"]) != item.get("content_sha256"):
            raise ValidationError(f"EIP-{number} materialized-file hash mismatch")
    actual_files = {
        path.relative_to(package).as_posix() for path in package.rglob("*") if path.is_file()
    }
    if actual_files != expected_files:
        raise ValidationError(
            f"EIP-{number} package file set mismatch: expected={sorted(expected_files)}, "
            f"actual={sorted(actual_files)}"
        )

    prompt_path = PROMPT_ROOT / f"eip-{number}.md"
    operational = manifest.get("operational_files", {})
    if (
        operational.get("task_contract")
        != {"path": rel(TASK_CONTRACT), "content_sha256": file_sha256(TASK_CONTRACT)}
        or operational.get("assessment_contract")
        != {
            "path": rel(ASSESSMENT_CONTRACT),
            "content_sha256": file_sha256(ASSESSMENT_CONTRACT),
        }
        or operational.get("session_prompt")
        != {"path": rel(prompt_path), "content_sha256": file_sha256(prompt_path)}
        or operational.get("output_template_source")
        != {"path": rel(TASK05_TEMPLATE), "content_sha256": file_sha256(TASK05_TEMPLATE)}
    ):
        raise ValidationError(f"EIP-{number} operational-file provenance mismatch")

    if (
        template.get("task_id") != manifest["task_id"]
        or template.get("fork_id") != "hegota"
        or template.get("snapshot_id") != manifest["snapshot_id"]
        or template.get("eip") != manifest["eip"]
        or "snapshot_scope_summary" not in template.get("assessment", {})
        or "historical_scope_summary" in template.get("assessment", {})
        or "information_control" not in template
        or "hindsight_control" in template
    ):
        raise ValidationError(f"EIP-{number} output-template prospective schema mismatch")
    provenance = template.get("provenance", {})
    if provenance.get("input_package", {}).get("manifest_sha256") != file_sha256(
        manifest_path
    ):
        raise ValidationError(f"EIP-{number} template manifest hash mismatch")
    if provenance.get("session_prompt", {}).get("content_sha256") != file_sha256(prompt_path):
        raise ValidationError(f"EIP-{number} template prompt hash mismatch")
    if len(template.get("criteria", [])) != 28:
        raise ValidationError(f"EIP-{number} output template must contain 28 criteria")
    canonical_ids = [item["id"] for item in load_yaml(TASK05_TEMPLATE)["criteria"]]
    if [item.get("id") for item in template["criteria"]] != canonical_ids:
        raise ValidationError(f"EIP-{number} criterion order differs from Task 05")
    print(
        f"valid package Hegota EIP-{number}: sources={len(expected_sources)} "
        f"manifest={file_sha256(manifest_path)[:12]}"
    )


def validate_inventory() -> None:
    entries = expected_entries()
    expected = [int(item["eip"]) for item in entries]
    packages = sorted(
        int(path.name.removeprefix("eip-"))
        for path in PACKAGE_ROOT.glob("eip-*")
        if path.is_dir()
    )
    prompts = sorted(
        int(path.stem.removeprefix("eip-")) for path in PROMPT_ROOT.glob("eip-*.md")
    )
    if packages != sorted(expected) or prompts != sorted(expected):
        raise ValidationError(
            f"Scorable inventory mismatch: expected={expected}, packages={packages}, prompts={prompts}"
        )
    for number in expected:
        validate_package(PACKAGE_ROOT / f"eip-{number}")
    print(f"valid Hegota package inventory: packages={len(expected)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eip", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.eip is None:
        validate_inventory()
    else:
        validate_package(PACKAGE_ROOT / f"eip-{args.eip}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValidationError, KeyError, TypeError) as error:
        raise SystemExit(f"validation error: {error}") from error
