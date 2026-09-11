#!/usr/bin/env python3
"""Validate the two sealed SFI/CFI extension packages."""

from __future__ import annotations

import argparse
from pathlib import Path

import prepare_sfi_cfi as preparation
import validate_packages as engine
from engine_adapter import TASK_ROOT, package_engine


EXTENSION_ROOT = TASK_ROOT / "extensions" / "sfi-cfi-2026-08-26"
PACKAGE_ROOT = EXTENSION_ROOT / "inputs" / "packages"
PROMPT_ROOT = EXTENSION_ROOT / "inputs" / "prompts"
COHORT_PATH = EXTENSION_ROOT / "inputs" / "cohort.yaml"
REVIEW_PATH = EXTENSION_ROOT / "outputs" / "cohort-review.yaml"
PACKAGE_FREEZE = EXTENSION_ROOT / "outputs" / "package-manifest.yaml"
TASK_CONTRACT = EXTENSION_ROOT / "TASK.md"
EXPECTED_SNAPSHOT = "hegota-sfi-cfi-2026-08-26-ac450a4"
ValidationError = engine.ValidationError


def configure() -> None:
    engine.NAMESPACE = "hegota-sfi-cfi-2026-08-26"
    engine.PACKAGE_ROOT = PACKAGE_ROOT
    engine.PROMPT_ROOT = PROMPT_ROOT
    engine.COHORT_PATH = COHORT_PATH
    engine.REVIEW_PATH = REVIEW_PATH
    engine.TASK_CONTRACT = TASK_CONTRACT
    engine.PACKAGE_FREEZE = PACKAGE_FREEZE
    engine.EXPECTED_SNAPSHOT_ID = EXPECTED_SNAPSHOT


def validate_package(package: Path) -> None:
    configure()
    engine.validate_package(package)
    manifest = package_engine.load_yaml(package / "manifest.yaml")
    number = int(manifest["eip"]["number"])
    expected_status = {7805: "SFI", 8141: "CFI"}[number]
    if manifest.get("snapshot_selection_status") != expected_status:
        raise engine.ValidationError(f"EIP-{number} snapshot status mismatch")
    if manifest.get("preparation", {}).get("extension_adapter") != {
        "path": preparation.rel(preparation.ADAPTER_PATH),
        "content_sha256": package_engine.file_sha256(preparation.ADAPTER_PATH),
    }:
        raise engine.ValidationError(f"EIP-{number} extension-adapter provenance mismatch")
    expected_unavailable = [preparation.UNAVAILABLE_EIP_7562] if number == 8141 else []
    if manifest.get("unavailable_same_snapshot_links") != expected_unavailable:
        raise engine.ValidationError(f"EIP-{number} unavailable-link provenance mismatch")


def validate_inventory() -> None:
    configure()
    expected = [7805, 8141]
    packages = sorted(
        int(path.name.removeprefix("eip-"))
        for path in PACKAGE_ROOT.glob("eip-*")
        if path.is_dir()
    )
    prompts = sorted(
        int(path.stem.removeprefix("eip-")) for path in PROMPT_ROOT.glob("eip-*.md")
    )
    if packages != expected or prompts != expected:
        raise engine.ValidationError(
            f"Extension inventory mismatch: expected={expected}, packages={packages}, prompts={prompts}"
        )
    for number in expected:
        validate_package(PACKAGE_ROOT / f"eip-{number}")
    expected_freeze = package_engine.yaml_bytes(preparation.inventory())
    if not PACKAGE_FREEZE.is_file() or PACKAGE_FREEZE.read_bytes() != expected_freeze:
        raise engine.ValidationError("Extension package freeze is missing or differs")
    print("valid Hegota SFI/CFI package inventory: packages=2")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eip", type=int, choices=[7805, 8141])
    args = parser.parse_args()
    if args.eip is None:
        validate_inventory()
    else:
        validate_package(PACKAGE_ROOT / f"eip-{args.eip}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (engine.ValidationError, KeyError, TypeError) as error:
        raise SystemExit(f"extension package validation error: {error}") from error
