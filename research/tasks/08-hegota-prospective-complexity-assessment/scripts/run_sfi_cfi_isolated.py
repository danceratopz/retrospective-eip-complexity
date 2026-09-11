#!/usr/bin/env python3
"""Run one SFI/CFI extension assessment through the Task 05 isolation engine."""

from __future__ import annotations

import sys
from pathlib import Path

from engine_adapter import TASK_ROOT, load_engine_module
from validate_sfi_cfi_assessment import (
    ValidationError as OutputValidationError,
    package_paths,
    validate,
)
from validate_sfi_cfi_packages import (
    ValidationError as InputValidationError,
    validate_package,
)


engine = load_engine_module("run_isolated")
engine.TASK_ROOT = TASK_ROOT
engine.TASK_CONTRACT = TASK_ROOT / "prompts" / "ASSESSMENT-CONTRACT.md"
engine.CONTRACT_CAPSULE_NAME = "ASSESSMENT-CONTRACT.md"
engine.CAPSULE_PARENT = Path("/tmp/hegota-sfi-cfi-complexity-assessment-runs")
engine.LOCK_PARENT = Path("/tmp/hegota-sfi-cfi-complexity-assessment-locks")
engine.package_paths = package_paths
engine.validate = validate
engine.validate_package = lambda _fork_id, package: validate_package(package)
engine.checklist_path = lambda _fork_id: None
engine.tick = lambda _path, number: print(
    f"Task 08 SFI/CFI EIP-{number} completion is recorded by the canonical assessment"
)


def main() -> int:
    if "--fork" not in sys.argv:
        sys.argv[1:1] = ["--fork", "hegota"]
    return engine.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        engine.LaunchError,
        InputValidationError,
        OutputValidationError,
        engine.CompletionError,
    ) as error:
        raise SystemExit(f"extension isolated launch error: {error}") from error
