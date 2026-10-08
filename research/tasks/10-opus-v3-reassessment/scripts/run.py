#!/usr/bin/env python3
"""Run the Task 10 assessments through the sandboxed `claude -p` engine, resuming completed calls.

    run.py --only shanghai/3855 amsterdam/7928 hegota/8141   # pilot
    run.py                                                   # every package; historical first
    run.py --convert-only                                    # rebuild assessment YAML from raw responses
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import common
from common import InputError, file_sha256, load_yaml, sha256, yaml_bytes
from engine_adapter import REPO_ROOT, TASK_ROOT
from validate import ValidationError, cases, validate


FROZEN = ["TASK.md", "config.yaml", "prompts", "inputs", "scripts", "retrospective/inputs", "prospective/inputs"]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True, check=True).stdout.strip()


def rebuild_prompt(case: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Rebuild the prompt from the sealed package and refuse it if its hash differs from the manifest."""
    package = case["package"]
    manifest = load_yaml(package / "manifest.yaml")
    request = manifest["request"]
    documents = [
        (item["path"], item["role"], (package / item["path"]).read_text(encoding="utf-8"))
        for item in request["documents"]
    ]
    prompt = common.render_prompt(
        identity=request["identity"],
        documents=documents,
        rubric_view=(package / "rubric.md").read_text(encoding="utf-8"),
        candidates=request["candidate_interacting_eips"],
    )
    if sha256(prompt.encode()) != request["prompt_sha256"]:
        raise InputError(f"{case['key']}: rendered prompt differs from the frozen hash")
    schema_path = package / request["schema"]["path"]
    if file_sha256(schema_path) != request["schema"]["content_sha256"]:
        raise InputError(f"{case['key']}: schema differs from the frozen hash")
    return prompt, read_json(schema_path), manifest


def convert_case(case: dict[str, Any]) -> str:
    manifest = load_yaml(case["package"] / "manifest.yaml")
    raw = read_json(case["raw"])
    _, rubric_manifest = common.frozen_rubric()
    result = common.convert(
        raw=raw,
        raw_path=case["raw"],
        template=load_yaml(case["package"] / "output-template.yaml"),
        rubric=rubric_manifest["parsed"],
        candidates=manifest["request"]["candidate_interacting_eips"],
        scope_field="snapshot_scope_summary" if case["mode"] == "prospective" else "historical_scope_summary",
        runtime=common.config()["runtime"],
    )
    case["output"].parent.mkdir(parents=True, exist_ok=True)
    case["output"].write_bytes(yaml_bytes(result))
    total, tier = validate(case)
    return f"{case['key']} total={total} tier={tier}"


def run_case(case: dict[str, Any], runtime: dict[str, Any], system_prompt: str, version: str) -> str:
    prompt, schema, manifest = rebuild_prompt(case)
    if case["raw"].is_file():
        raw = read_json(case["raw"])
        if raw.get("ok") and raw.get("prompt_sha256") == manifest["request"]["prompt_sha256"]:
            return f"kept {convert_case(case)}"
        raise InputError(f"{case['key']}: existing raw response does not match this package; move it aside first")
    record = common.call(runtime, system_prompt, prompt, schema)
    record = {
        "case": case["key"],
        "run_id": f"assessment-run-{uuid.uuid4()}",
        "claude_code_version": version,
        **record,
    }
    if not record["ok"]:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        failed = case["failed"] / f"eip-{case['number']}-{stamp}.json"
        write_json(failed, record)
        return f"FAILED {case['key']} (kept {failed.relative_to(TASK_ROOT)}; rerun retries)"
    write_json(case["raw"], record)
    try:
        return f"done {convert_case(case)}"
    except (InputError, ValidationError, KeyError, TypeError) as error:
        return f"INVALID {case['key']}: {error} (raw kept; fix conversion and use --convert-only)"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="fork/eip keys, for example shanghai/3855 hegota/8141")
    parser.add_argument("--mode", choices=["retrospective", "prospective"])
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--convert-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = [
        case for case in cases()
        if (not args.only or case["key"] in args.only) and (not args.mode or case["mode"] == args.mode)
    ]  # fmt: skip
    if args.only and len(selected) != len(set(args.only)):
        raise InputError(f"Unknown keys: {sorted(set(args.only) - {case['key'] for case in selected})}")
    if args.convert_only:
        for case in selected:
            if case["raw"].is_file():
                print(convert_case(case), flush=True)
        return 0

    dirty = git("status", "--porcelain", "--", *[str(TASK_ROOT / path) for path in FROZEN])
    if dirty:
        raise InputError(f"Commit the frozen Task 10 inputs and scripts before inference:\n{dirty}")
    config = common.config()
    runtime = config["runtime"]
    version = common.claude_version()
    system_prompt = common.SYSTEM_PROMPT.read_text(encoding="utf-8")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    pending = [case for case in selected if not case["raw"].is_file()]
    write_json(
        TASK_ROOT / "runs" / f"{stamp}.json",
        {
            "started_at": common.now(),
            "repository_commit": git("rev-parse", "HEAD"),
            "claude_code_version": version,
            "model": runtime["model"],
            "effort": runtime["effort"],
            "claude_flags": runtime["claude_flags"],
            "isolation_method": common.ISOLATION_METHOD,
            "selected": [case["key"] for case in selected],
            "pending_calls": [case["key"] for case in pending],
        },
    )
    print(f"{len(selected)} selected, {len(pending)} calls pending; Claude Code {version}", flush=True)
    failures = 0
    with ThreadPoolExecutor(max_workers=args.jobs or runtime["maximum_concurrency"]) as pool:
        futures = {pool.submit(run_case, case, runtime, system_prompt, version): case for case in selected}
        for future in as_completed(futures):
            try:
                message = future.result()
            except Exception as error:  # keep other cases going; a rerun resumes
                message = f"ERROR {futures[future]['key']}: {error}"
            failures += message.startswith(("FAILED", "INVALID", "ERROR"))
            print(message, flush=True)
    print(f"finished with {failures} failed or invalid cases", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as error:
        raise SystemExit(f"input error: {error}") from error
