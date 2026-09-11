#!/usr/bin/env python3
"""Validate one completed SFI/CFI extension assessment."""

from __future__ import annotations

import argparse
from pathlib import Path

import validate_assessment as engine
import validate_sfi_cfi_packages as input_validator
from engine_adapter import TASK_ROOT, output_engine


EXTENSION_ROOT = TASK_ROOT / "extensions" / "sfi-cfi-2026-08-26"
NAMESPACE = "hegota-sfi-cfi-2026-08-26"
PACKAGE_ROOT = EXTENSION_ROOT / "inputs" / "packages"
PROMPT_ROOT = EXTENSION_ROOT / "inputs" / "prompts"
OUTPUT_ROOT = EXTENSION_ROOT / "outputs" / "assessments"
RAW_ROOT = EXTENSION_ROOT / "outputs" / "raw"
EXPECTED_SNAPSHOT = "hegota-sfi-cfi-2026-08-26-ac450a4"
ValidationError = engine.ValidationError


def configure() -> None:
    input_validator.configure()
    engine.NAMESPACE = NAMESPACE
    engine.PACKAGE_ROOT = PACKAGE_ROOT
    engine.PROMPT_ROOT = PROMPT_ROOT
    engine.OUTPUT_ROOT = OUTPUT_ROOT
    engine.RAW_ROOT = RAW_ROOT
    engine.EXPECTED_SNAPSHOT_ID = EXPECTED_SNAPSHOT


def package_paths(_fork_id: str, number: int) -> tuple[Path, Path, Path, Path]:
    configure()
    package = PACKAGE_ROOT / f"eip-{number}"
    output = OUTPUT_ROOT / f"eip-{number}.yaml"
    prompt = PROMPT_ROOT / f"eip-{number}.md"
    return package, output, prompt, package / "output-template.yaml"


def validate(_fork_id: str, number: int, output_override: Path | None = None) -> Path:
    configure()
    engine.package_paths = package_paths
    return engine.validate("hegota", number, output_override)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eip", required=True, type=int, choices=[7805, 8141])
    parser.add_argument("--output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    validate("hegota", args.eip, args.output)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (engine.ValidationError, output_engine.ValidationError, KeyError, TypeError) as error:
        raise SystemExit(f"extension assessment validation error: {error}") from error
