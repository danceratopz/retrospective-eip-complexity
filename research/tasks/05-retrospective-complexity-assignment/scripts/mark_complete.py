#!/usr/bin/env python3
"""Validate an EIP assessment and safely tick its shared checklist item."""

from __future__ import annotations

import argparse
import fcntl
import os
import re
import stat
import tempfile
from pathlib import Path

import yaml

from validate_output import ValidationError, validate


TASK_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = TASK_ROOT / "config.yaml"
LOCK_PATH = Path("/tmp/retrospective-complexity-eval-osaka-checklist.lock")


class CompletionError(RuntimeError):
    """Raised when the validated assessment cannot be marked complete."""


def checklist_path(fork_id: str) -> Path | None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    vault = config.get("vault", {})
    configured = vault.get("checklists", {}).get(fork_id)
    if configured is None and fork_id == "osaka":
        configured = vault.get("osaka_checklist")
    return Path(configured) if configured else None


def tick(path: Path | None, number: int) -> None:
    if path is None:
        print(
            f"no shared checklist configured for EIP-{number}; "
            "the validated canonical output is the completion record"
        )
        return
    if not path.is_file():
        raise CompletionError(f"Vault checklist is missing: {path}")
    unchecked = re.compile(rf"(?m)^- \[ \] EIP-{number}\b")
    checked = re.compile(rf"(?m)^- \[x\] EIP-{number}\b")

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        original = path.read_text(encoding="utf-8")
        if checked.search(original):
            print(f"already complete in shared checklist: EIP-{number}")
            return
        matches = unchecked.findall(original)
        if len(matches) != 1:
            raise CompletionError(
                f"Expected exactly one unchecked EIP-{number} item, found {len(matches)}"
            )
        updated = unchecked.sub(f"- [x] EIP-{number}", original, count=1)
        mode = stat.S_IMODE(path.stat().st_mode)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary.write(updated)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.chmod(temporary_path, mode)
        os.replace(temporary_path, path)
        print(f"marked complete in shared checklist: EIP-{number}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fork", required=True)
    parser.add_argument("--eip", required=True, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate(args.fork, args.eip)
    tick(checklist_path(args.fork), args.eip)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValidationError, CompletionError) as error:
        raise SystemExit(f"completion error: {error}") from error
