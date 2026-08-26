#!/usr/bin/env python3
"""Run the Task 08 cohort through the shared bounded-concurrency orchestrator."""

from __future__ import annotations

import sys

from engine_adapter import TASK_ROOT, load_engine_module
from validate_assessment import OUTPUT_ROOT
from validate_packages import PACKAGE_ROOT


engine = load_engine_module("run_fork")
engine.TASK_ROOT = TASK_ROOT
engine.RUN_ISOLATED = TASK_ROOT / "scripts" / "run_isolated.py"
engine.RUNS_ROOT = TASK_ROOT / "runs"
engine.RUN_TASK_ID = "08-hegota-prospective-complexity-assessment-run"


def package_numbers(_fork_id: str) -> list[int]:
    numbers = sorted(
        int(path.name.removeprefix("eip-"))
        for path in PACKAGE_ROOT.glob("eip-*")
        if path.is_dir()
    )
    if not numbers:
        raise engine.OrchestrationError("No prepared Task 08 packages found")
    return numbers


def output_path(_fork_id: str, number: int):
    return OUTPUT_ROOT / f"eip-{number}.yaml"


engine.package_numbers = package_numbers
engine.output_path = output_path


def main() -> int:
    if "--fork" not in sys.argv:
        sys.argv[1:1] = ["--fork", "hegota"]
    if "--jobs" not in sys.argv:
        sys.argv.extend(["--jobs", "3"])
    jobs_index = sys.argv.index("--jobs") + 1
    if int(sys.argv[jobs_index]) > 3:
        raise engine.OrchestrationError("Task 08 permits at most three concurrent assessors")
    return engine.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except engine.OrchestrationError as error:
        raise SystemExit(f"orchestration error: {error}") from error
