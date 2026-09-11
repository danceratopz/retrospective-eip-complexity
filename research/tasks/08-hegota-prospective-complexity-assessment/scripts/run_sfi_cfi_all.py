#!/usr/bin/env python3
"""Run both SFI/CFI extension assessments with bounded concurrency."""

from __future__ import annotations

import sys

from engine_adapter import TASK_ROOT, load_engine_module
from validate_sfi_cfi_assessment import OUTPUT_ROOT
from validate_sfi_cfi_packages import PACKAGE_ROOT


engine = load_engine_module("run_fork")
engine.TASK_ROOT = TASK_ROOT
engine.RUN_ISOLATED = TASK_ROOT / "scripts" / "run_sfi_cfi_isolated.py"
engine.RUNS_ROOT = TASK_ROOT / "extensions" / "sfi-cfi-2026-08-26" / "runs"
engine.RUN_TASK_ID = "08-hegota-prospective-complexity-assessment-sfi-cfi-run"


def package_numbers(_fork_id: str) -> list[int]:
    numbers = sorted(
        int(path.name.removeprefix("eip-"))
        for path in PACKAGE_ROOT.glob("eip-*")
        if path.is_dir()
    )
    if numbers != [7805, 8141]:
        raise engine.OrchestrationError(f"Expected extension packages [7805, 8141], found {numbers}")
    return numbers


def output_path(_fork_id: str, number: int):
    return OUTPUT_ROOT / f"eip-{number}.yaml"


engine.package_numbers = package_numbers
engine.output_path = output_path


def main() -> int:
    if "--fork" not in sys.argv:
        sys.argv[1:1] = ["--fork", "hegota"]
    if "--jobs" not in sys.argv:
        sys.argv.extend(["--jobs", "2"])
    jobs_index = sys.argv.index("--jobs") + 1
    if int(sys.argv[jobs_index]) > 3:
        raise engine.OrchestrationError("Task 08 permits at most three concurrent assessors")
    return engine.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except engine.OrchestrationError as error:
        raise SystemExit(f"extension orchestration error: {error}") from error
