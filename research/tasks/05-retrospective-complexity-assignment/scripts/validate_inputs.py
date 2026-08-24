#!/usr/bin/env python3
"""Validate sealed Task 05 packages before assessment sessions start."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

import yaml


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK04_ROOT = REPO_ROOT / "research" / "tasks" / "04-complexity-assessment-ref-selection"


class ValidationError(RuntimeError):
    """Raised when a sealed input package is inconsistent."""


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValidationError(f"Expected a YAML mapping: {path}")
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_package(fork_id: str, package: Path) -> None:
    manifest_path = package / "manifest.yaml"
    template_path = package / "output-template.yaml"
    manifest = load_yaml(manifest_path)
    template = load_yaml(template_path)
    number = int(manifest.get("eip", {}).get("number", -1))
    if manifest.get("fork_id") != fork_id or package.name != f"eip-{number}":
        raise ValidationError(f"Package identity mismatch: {package}")

    ref_path = REPO_ROOT / manifest["task_04_ref"]["path"]
    ref = load_yaml(ref_path)
    if sha256(ref_path) != manifest["task_04_ref"]["content_sha256"]:
        raise ValidationError(f"EIP-{number} Task 04 ref hash mismatch")
    if ref.get("review", {}).get("status") != "approved":
        raise ValidationError(f"EIP-{number} Task 04 ref is no longer approved")

    eip_path = package / manifest["historical_eip"]["package_path"]
    if sha256(eip_path) != manifest["historical_eip"]["content_sha256"]:
        raise ValidationError(f"EIP-{number} historical EIP hash mismatch")
    rubric_path = package / manifest["rubric"]["package_path"]
    if sha256(rubric_path) != manifest["rubric"]["assessor_view_sha256"]:
        raise ValidationError(f"EIP-{number} assessor-view hash mismatch")
    rubric_text = rubric_path.read_text(encoding="utf-8")
    if "Amsterdam calibration" in rubric_text or "##### Revision Notes" in rubric_text:
        raise ValidationError(f"EIP-{number} package exposes retrospective rubric notes")

    expected_sources = ["eip.md", "rubric.md"]
    for supporting in manifest.get("supporting_documents", []):
        path = package / supporting["package_path"]
        if sha256(path) != supporting["content_sha256"]:
            raise ValidationError(f"EIP-{number} supporting-document hash mismatch: {path}")
        expected_sources.append(supporting["package_path"])
    if manifest.get("assessment_source_files") != expected_sources:
        raise ValidationError(f"EIP-{number} assessment source allowlist mismatch")

    prompt_path = TASK_ROOT / "prompts" / fork_id / f"eip-{number}.md"
    if not prompt_path.is_file():
        raise ValidationError(f"EIP-{number} prompt is missing")
    provenance = template.get("provenance", {})
    if provenance.get("input_package", {}).get("manifest_sha256") != sha256(manifest_path):
        raise ValidationError(f"EIP-{number} template manifest hash mismatch")
    if provenance.get("session_prompt", {}).get("content_sha256") != sha256(prompt_path):
        raise ValidationError(f"EIP-{number} template prompt hash mismatch")
    if template.get("eip") != manifest.get("eip") or template.get("fork_id") != fork_id:
        raise ValidationError(f"EIP-{number} output-template identity mismatch")
    if len(template.get("criteria", [])) != 28:
        raise ValidationError(f"EIP-{number} output template must contain 28 criteria")
    print(
        f"valid package {fork_id} EIP-{number}: "
        f"sources={len(expected_sources)} manifest={sha256(manifest_path)[:12]}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fork", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    package_root = TASK_ROOT / "inputs" / "fork-eips" / args.fork
    packages = sorted(path for path in package_root.glob("eip-*") if path.is_dir())
    refs = sorted(
        (TASK04_ROOT / "outputs" / "fork-eips" / args.fork).glob("eip-*.yaml")
    )
    if not packages:
        raise ValidationError(f"No packages found for {args.fork}")
    package_numbers = {int(path.name.removeprefix("eip-")) for path in packages}
    approved_numbers = {
        int(path.stem.removeprefix("eip-"))
        for path in refs
        if load_yaml(path).get("review", {}).get("status") == "approved"
    }
    if package_numbers != approved_numbers:
        raise ValidationError(
            f"Package inventory differs from approved Task 04 refs: "
            f"packages={sorted(package_numbers)}, approved={sorted(approved_numbers)}"
        )
    for package in packages:
        validate_package(args.fork, package)
    print(f"valid fork inventory {args.fork}: packages={len(packages)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as error:
        raise SystemExit(f"validation error: {error}") from error

