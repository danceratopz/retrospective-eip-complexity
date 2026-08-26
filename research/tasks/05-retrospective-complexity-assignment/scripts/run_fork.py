#!/usr/bin/env python3
"""Run all pending Task 05 EIP assessments for one fork with bounded concurrency."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


TASK_ROOT = Path(__file__).resolve().parents[1]
RUN_ISOLATED = TASK_ROOT / "scripts" / "run_isolated.py"
RUNS_ROOT = TASK_ROOT / "runs"
RUN_TASK_ID = "05-retrospective-complexity-assignment-fork-run"


class OrchestrationError(RuntimeError):
    """Raised when a fork assessment run cannot be planned safely."""


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def package_numbers(fork_id: str) -> list[int]:
    root = TASK_ROOT / "inputs" / "fork-eips" / fork_id
    numbers = sorted(
        int(path.name.removeprefix("eip-"))
        for path in root.glob("eip-*")
        if path.is_dir()
    )
    if not numbers:
        raise OrchestrationError(f"No prepared packages found for fork {fork_id}")
    return numbers


def output_path(fork_id: str, number: int) -> Path:
    return TASK_ROOT / "outputs" / "fork-eips" / fork_id / f"eip-{number}.yaml"


def atomic_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as temporary:
        yaml.safe_dump(data, temporary, sort_keys=False, allow_unicode=True, width=100)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def run_one(fork_id: str, number: int, log_path: Path) -> int:
    command = [
        sys.executable,
        str(RUN_ISOLATED),
        "--fork",
        fork_id,
        "--eip",
        str(number),
    ]
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


def enrich_record(fork_id: str, record: dict[str, Any], run_dir: Path) -> None:
    number = int(record["eip"])
    assessment_path = output_path(fork_id, number)
    if assessment_path.is_file():
        assessment = yaml.safe_load(assessment_path.read_text(encoding="utf-8"))
        record["score"] = assessment["totals"]["primary_score"]
        record["tier"] = assessment["totals"]["complexity_tier"]
        record["overall_confidence"] = assessment["overall_confidence"]
    log_text = (run_dir / record["log"]).read_text(encoding="utf-8")
    matches = re.findall(r"tokens used\n([0-9,]+)", log_text)
    if matches:
        record["tokens_used"] = int(matches[-1].replace(",", ""))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fork", required=True)
    parser.add_argument("--eip", action="append", type=int)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show the pending sessions without launching Codex",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.jobs < 1:
        raise OrchestrationError("--jobs must be at least 1")

    available = package_numbers(args.fork)
    if args.eip:
        requested = sorted(set(args.eip))
        missing = sorted(set(requested) - set(available))
        if missing:
            raise OrchestrationError(f"No prepared packages for EIPs: {missing}")
    else:
        requested = available

    completed = [number for number in requested if output_path(args.fork, number).is_file()]
    pending = [number for number in requested if number not in completed]
    print(f"fork: {args.fork}")
    print(f"already complete: {completed or 'none'}")
    print(f"pending: {pending or 'none'}")
    print(f"maximum concurrent sessions: {min(args.jobs, len(pending)) if pending else 0}")
    if args.dry_run or not pending:
        return 0

    run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNS_ROOT / f"{run_stamp}-{args.fork}"
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = run_dir / "manifest.yaml"
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "task_id": RUN_TASK_ID,
        "fork_id": args.fork,
        "started_at": now(),
        "finished_at": None,
        "model": "gpt-5.6-sol",
        "reasoning_effort": "xhigh",
        "execution_mode": "isolated_non_interactive",
        "maximum_concurrency": args.jobs,
        "completed_before_run": completed,
        "sessions": [
            {
                "eip": number,
                "status": "pending",
                "exit_code": None,
                "log": f"eip-{number}.log",
            }
            for number in pending
        ],
    }
    atomic_yaml(manifest_path, manifest)
    records = {item["eip"]: item for item in manifest["sessions"]}

    failures: list[int] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures: dict[Future[int], int] = {}
        for number in pending:
            records[number]["status"] = "running"
            future = executor.submit(run_one, args.fork, number, run_dir / f"eip-{number}.log")
            futures[future] = number
        atomic_yaml(manifest_path, manifest)

        for future in as_completed(futures):
            number = futures[future]
            try:
                returncode = future.result()
            except Exception as error:  # pragma: no cover - defensive process boundary
                returncode = 1
                records[number]["error"] = str(error)
            records[number]["exit_code"] = returncode
            records[number]["status"] = "completed" if returncode == 0 else "failed"
            if returncode:
                failures.append(number)
                print(f"failed EIP-{number}; inspect {run_dir / f'eip-{number}.log'}", flush=True)
            else:
                print(f"completed EIP-{number}", flush=True)
            atomic_yaml(manifest_path, manifest)

    recovered = [
        number for number in failures if output_path(args.fork, number).is_file()
    ]
    unresolved = [number for number in failures if number not in recovered]
    for number in recovered:
        records[number]["status"] = "recovered"
        records[number]["recovery"] = "validated canonical output collected after child exit"
    for record in manifest["sessions"]:
        enrich_record(args.fork, record, run_dir)
    manifest["finished_at"] = now()
    if unresolved:
        manifest["status"] = "failed"
    elif recovered:
        manifest["status"] = "completed_with_recoveries"
    else:
        manifest["status"] = "completed"
    manifest["failed_eips"] = unresolved
    manifest["recovered_eips"] = recovered
    manifest["total_tokens_used"] = sum(
        int(record.get("tokens_used", 0)) for record in manifest["sessions"]
    )
    atomic_yaml(manifest_path, manifest)
    print(f"run manifest: {manifest_path}")
    if unresolved:
        raise OrchestrationError(f"Failed EIP sessions: {unresolved}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OrchestrationError as error:
        raise SystemExit(f"orchestration error: {error}") from error
