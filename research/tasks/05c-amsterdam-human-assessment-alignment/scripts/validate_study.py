#!/usr/bin/env python3
"""Validate the complete frozen Task 05c dataset and derived study outputs."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import (
    AUTOMATED_ROOT,
    COMPARISON_ROOT,
    DATASET_MANIFEST_PATH,
    FREEZE_PATH,
    INVENTORY_PATH,
    REPO_ROOT,
    SUMMARY_PATH,
    TASK_ROOT,
    StudyError,
    load_yaml,
    parse_time,
    rel,
    sha256_file,
    write_yaml,
)
from compare import build_comparison, build_summary, dataset_manifest, metrics
from run_isolated import codex_inner_command
from validate_inputs import main as validate_inputs
from validate_outputs import validate_automated, validate_freeze


REPORT_PATH = TASK_ROOT / "outputs/validation-report.yaml"
ISOLATION_REPORT_PATH = TASK_ROOT / "outputs/isolation-self-test.yaml"
RECOVERY_AUDIT_PATH = TASK_ROOT / "outputs/recovery-audit.yaml"
RUNS_ROOT = TASK_ROOT / "outputs/runs"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StudyError(message)


def validate_isolation_record() -> None:
    record = load_yaml(ISOLATION_REPORT_PATH)
    require(record.get("status") == "passed", "Isolation self-test did not pass")
    require(record.get("no_assessor_launched") is True, "Isolation probe launched an assessor")
    require(record.get("no_canonical_output_written") is True, "Isolation probe wrote an output")
    require(
        record.get("completed_before_first_real_run") is True,
        "Isolation probe is not recorded as pre-assessment",
    )
    checks = record.get("checks")
    require(
        isinstance(checks, dict) and checks and set(checks.values()) == {"passed"},
        "One or more isolation checks did not pass",
    )
    for key in (
        "exact_positive_filesystem_allowlist",
        "repository_root_hidden",
        "pm_repository_hidden",
        "task_05_outputs_hidden",
        "human_inputs_hidden",
        "comparison_outputs_hidden",
        "other_eip_capsules_hidden",
        "global_codex_state_hidden_except_minimal_auth_and_ephemeral_config",
        "direct_network_denied_inside_codex_tool_sandbox",
        "codex_web_search_disabled",
        "inherited_mcp_apps_plugins_skills_disabled",
        "approval_policy_never",
    ):
        require(checks.get(key) == "passed", f"Missing required isolation check: {key}")
    launcher = REPO_ROOT / record["launcher"]["path"]
    package = REPO_ROOT / record["test_package"]["manifest_path"]
    require(sha256_file(launcher) == record["launcher"]["sha256"], "Isolation launcher hash changed")
    require(sha256_file(package) == record["test_package"]["manifest_sha256"], "Isolation test package hash changed")
    run_manifests = sorted(RUNS_ROOT.glob("*/manifest.yaml"))
    require(bool(run_manifests), "No real-run manifest exists")
    first_real_run = min(parse_time(load_yaml(path)["started_at"]) for path in run_manifests)
    require(parse_time(record["run_at"]) < first_real_run, "Isolation self-test did not precede the first real run")


def validate_recovery_audit() -> None:
    audit = load_yaml(RECOVERY_AUDIT_PATH)
    require(
        audit.get("status") == "resolved_without_assessor_output_modification",
        "Recovery audit status is invalid",
    )
    require(audit.get("fresh_assessor_reruns") == 0, "Recovery audit records an assessor rerun")
    require(audit.get("score_or_rationale_changes") == 0, "Recovery audit records a score/rationale change")
    validator = REPO_ROOT / audit["corrected_validator"]["path"]
    require(
        sha256_file(validator) == audit["corrected_validator"]["sha256"],
        "Recovery-audit validator hash changed",
    )
    recoveries = audit.get("recoveries")
    require(isinstance(recoveries, list), "Recovery audit entries are invalid")
    require(
        {int(item["eip"]) for item in recoveries} == {2780, 7610, 7708, 7778, 7843},
        "Recovery audit EIP inventory differs",
    )
    for item in recoveries:
        number = int(item["eip"])
        canonical = REPO_ROOT / item["canonical_output"]
        require(canonical.is_file(), f"Recovered EIP-{number} canonical output is missing")
        canonical_hash = sha256_file(canonical)
        require(
            canonical_hash == item["canonical_output_sha256"] == item["assessor_output_sha256"],
            f"Recovered EIP-{number} bytes differ from the assessor output",
        )
        result = load_yaml(canonical)
        require(
            result["provenance"]["assessor_environment"]["session_id"] == item["session_id"],
            f"Recovered EIP-{number} session provenance differs",
        )
        require((REPO_ROOT / item["original_run_log"]).is_file(), f"Recovered EIP-{number} run log is missing")


def validate_assessor_environment(number: int, result: dict[str, Any]) -> str:
    environment = result["provenance"]["assessor_environment"]
    executable = Path(environment["codex_executable_path"])
    require(executable.is_file(), f"EIP-{number} recorded Codex executable is missing")
    require(
        sha256_file(executable) == environment["codex_binary_sha256"],
        f"EIP-{number} recorded Codex binary hash differs from the executable",
    )
    require(environment["command"] == codex_inner_command(), f"EIP-{number} assessor command differs")
    require(environment["agent_identity"] == "Codex", f"EIP-{number} agent identity differs")
    return environment["session_id"]


def validate_comparisons(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    included = [item for item in inventory["eips"] if item["status"] == "included"]
    expected_paths = {COMPARISON_ROOT / f"eip-{int(item['eip']['number'])}.yaml" for item in included}
    actual_paths = set(COMPARISON_ROOT.glob("eip-*.yaml"))
    require(actual_paths == expected_paths, "Comparison output inventory differs from included EIPs")
    freeze = load_yaml(FREEZE_PATH)
    freeze_time = parse_time(freeze["frozen_at"])
    records: list[dict[str, Any]] = []
    for item in included:
        number = int(item["eip"]["number"])
        path = COMPARISON_ROOT / f"eip-{number}.yaml"
        actual = load_yaml(path)
        expected = build_comparison(item)
        require(
            parse_time(actual["provenance"]["generated_at"]) >= freeze_time,
            f"EIP-{number} comparison predates the automated freeze",
        )
        expected["provenance"]["generated_at"] = actual["provenance"]["generated_at"]
        require(actual == expected, f"EIP-{number} comparison fields or deltas are stale")
        records.append(actual)
    return records


def validate_dataset_manifest(inventory: dict[str, Any]) -> None:
    actual = load_yaml(DATASET_MANIFEST_PATH)
    expected = dataset_manifest(inventory)
    expected["generated_at"] = actual.get("generated_at")
    require(actual == expected, "Dataset manifest inventory or recorded hashes are stale")
    paths: set[str] = set()
    for entry in actual["files"]:
        path_text = entry["path"]
        require(path_text not in paths, f"Duplicate dataset-manifest path: {path_text}")
        paths.add(path_text)
        path = REPO_ROOT / path_text
        require(path.is_file(), f"Dataset-manifest file is missing: {path_text}")
        require(sha256_file(path) == entry["sha256"], f"Dataset-manifest hash changed: {path_text}")


def report_payload(inventory: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    clean = [record for record in records if record["clean_comparison"]["eligible"]]
    sessions = {
        load_yaml(AUTOMATED_ROOT / f"eip-{int(item['eip']['number'])}.yaml")["provenance"]
        ["assessor_environment"]["session_id"]
        for item in inventory["eips"]
        if item["status"] == "included"
    }
    return {
        "schema_version": 1,
        "task_id": "05c-amsterdam-human-assessment-alignment-validation",
        "status": "passed",
        "population": {
            "approved_task_04": inventory["counts"]["approved_task_04"],
            "included": inventory["counts"]["included"],
            "excluded": inventory["counts"]["excluded"],
            "clean": len(clean),
        },
        "automated_sessions": {
            "count": len(sessions),
            "all_unique": len(sessions) == inventory["counts"]["included"],
            "model": "gpt-5.6-sol",
            "reasoning_effort": "xhigh",
        },
        "alignment_metrics": {
            "all": metrics(records),
            "clean": metrics(clean),
        },
        "checks": [
            "approved Amsterdam population mechanically rederived from Task 04",
            "Task 04 refs and Task 05 package/output joins retain their recorded hashes",
            "included and excluded records exhaust the approved population",
            "human assessment, historical rubric, and human-time EIP blobs and timestamps verified from Git",
            "human score cells reparsed with blanks accepted as zero only when published arithmetic proves zero",
            "automated capsules match the Task 05 source allowlist with only the controlled rubric/template replacement",
            "capsule manifests, prompts, and contracts contain no forbidden human or current-score markers",
            "one unique isolated gpt-5.6-sol xhigh session is recorded for every automated result",
            "automated totals, nominal maxima, tiers, hindsight attestations, and evidence allowlists recomputed",
            "pre-run no-token filesystem and network isolation self-test verified",
            "immutable automated freeze validated before comparison access",
            "comparison observations, per-anchor deltas, rubric mappings, aggregate statistics, and summary recomputed",
            "dataset file inventory and every recorded content hash recomputed",
        ],
    }


def validate_all() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    require(validate_inputs() == 0, "Input validation did not complete")
    validate_isolation_record()
    validate_recovery_audit()
    inventory = load_yaml(INVENTORY_PATH)
    included = [item for item in inventory["eips"] if item["status"] == "included"]
    sessions: set[str] = set()
    for item in included:
        number = int(item["eip"]["number"])
        output = validate_automated(number)
        session = validate_assessor_environment(number, load_yaml(output))
        require(session not in sessions, f"Automated session ID reused: {session}")
        sessions.add(session)
    require(len(sessions) == len(included), "Automated result/session count mismatch")
    validate_freeze()
    records = validate_comparisons(inventory)
    expected_summary = build_summary(inventory, records).encode()
    require(SUMMARY_PATH.read_bytes() == expected_summary, "Alignment summary is stale")
    validate_dataset_manifest(inventory)
    return inventory, records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inventory, records = validate_all()
    if args.write_report:
        write_yaml(REPORT_PATH, report_payload(inventory, records))
        # The report is deterministic and deliberately contains no manifest hash,
        # so it can be added to the self-describing dataset without a hash cycle.
        write_yaml(DATASET_MANIFEST_PATH, dataset_manifest(inventory))
        validate_dataset_manifest(inventory)
    print(
        f"valid complete study: included={len(records)} "
        f"clean={sum(record['clean_comparison']['eligible'] for record in records)} "
        f"freeze={rel(FREEZE_PATH)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except StudyError as error:
        raise SystemExit(f"study validation error: {error}") from error
