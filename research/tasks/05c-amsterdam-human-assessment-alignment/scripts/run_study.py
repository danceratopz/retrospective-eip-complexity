#!/usr/bin/env python3
"""Run all pending Task 05c assessors with a hard three-session concurrency cap."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from common import AUTOMATED_ROOT, INVENTORY_PATH, TASK_ROOT, StudyError, load_yaml, now
from validate_outputs import create_freeze


RUN_ISOLATED = TASK_ROOT / "scripts/run_isolated.py"
RUNS_ROOT = TASK_ROOT / "outputs/runs"


def atomic_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temporary:
        yaml.safe_dump(data, temporary, sort_keys=False, allow_unicode=True, width=100)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def run_one(number: int, log_path: Path) -> int:
    command = [sys.executable, str(RUN_ISOLATED), "--eip", str(number)]
    print(f"started EIP-{number}; log: {log_path}", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"started_at: {now()}\n")
        log.write(f"command: {' '.join(command)}\n\n")
        log.flush()
        result = subprocess.run(
            command,
            check=False,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log.write(f"\nfinished_at: {now()}\n")
        log.write(f"exit_code: {result.returncode}\n")
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eip", action="append", type=int)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.jobs <= 3:
        raise StudyError("--jobs must be between 1 and the study maximum of 3")
    inventory = load_yaml(INVENTORY_PATH)
    included = sorted(
        int(item["eip"]["number"])
        for item in inventory["eips"]
        if item["status"] == "included"
    )
    requested = sorted(set(args.eip)) if args.eip else included
    missing = sorted(set(requested) - set(included))
    if missing:
        raise StudyError(f"Requested EIPs are not in the included study population: {missing}")
    completed = [number for number in requested if (AUTOMATED_ROOT / f"eip-{number}.yaml").is_file()]
    pending = [number for number in requested if number not in completed]
    print(f"already complete: {completed or 'none'}")
    print(f"pending: {pending or 'none'}")
    print(f"maximum concurrent sessions: {min(args.jobs, len(pending)) if pending else 0}")
    if args.dry_run:
        return 0
    if not pending:
        if set(requested) == set(included):
            create_freeze()
        return 0

    run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_ROOT / run_stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = run_dir / "manifest.yaml"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "task_id": "05c-amsterdam-human-assessment-alignment-run",
        "started_at": now(),
        "finished_at": None,
        "model": "gpt-5.6-sol",
        "reasoning_effort": "xhigh",
        "maximum_concurrency": args.jobs,
        "completed_before_run": completed,
        "sessions": [
            {"eip": number, "status": "pending", "exit_code": None, "log": f"eip-{number}.log"}
            for number in pending
        ],
    }
    atomic_yaml(manifest_path, manifest)
    records = {int(item["eip"]): item for item in manifest["sessions"]}
    failures: list[int] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures: dict[Future[int], int] = {}
        for number in pending:
            records[number]["status"] = "running"
            futures[executor.submit(run_one, number, run_dir / f"eip-{number}.log")] = number
        atomic_yaml(manifest_path, manifest)
        for future in as_completed(futures):
            number = futures[future]
            try:
                returncode = future.result()
            except Exception as error:  # defensive process boundary
                returncode = 1
                records[number]["error"] = str(error)
            records[number]["exit_code"] = returncode
            records[number]["status"] = "completed" if returncode == 0 else "failed"
            if returncode:
                failures.append(number)
                print(f"failed EIP-{number}; inspect {run_dir / f'eip-{number}.log'}", flush=True)
            else:
                result = load_yaml(AUTOMATED_ROOT / f"eip-{number}.yaml")
                records[number]["score"] = result["totals"]["primary_score"]
                records[number]["tier"] = result["totals"]["complexity_tier"]
                records[number]["session_id"] = result["provenance"]["assessor_environment"]["session_id"]
                print(f"completed EIP-{number}", flush=True)
            atomic_yaml(manifest_path, manifest)
    manifest["finished_at"] = now()
    manifest["status"] = "failed" if failures else "completed"
    manifest["failed_eips"] = failures
    atomic_yaml(manifest_path, manifest)
    print(f"run manifest: {manifest_path}")
    if failures:
        raise StudyError(f"Failed EIP sessions: {failures}")
    if set(requested) == set(included):
        create_freeze()
        print("all included outputs validated and hash-frozen")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StudyError as error:
        raise SystemExit(f"study run error: {error}") from error
