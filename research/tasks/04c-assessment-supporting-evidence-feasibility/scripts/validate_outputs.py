#!/usr/bin/env python3
"""Validate Task 04c inventory, snapshots, blobs, classifications, and summaries."""

from __future__ import annotations

import hashlib
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


TASK_ID = "04c-assessment-supporting-evidence-feasibility"
TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK04_ROOT = REPO_ROOT / "research/tasks/04-complexity-assessment-ref-selection/outputs/fork-eips"
FORKS = ("shanghai", "cancun", "prague", "osaka", "amsterdam")
REPOSITORY_IDS = ("execution_specs", "execution_spec_tests")
MATURITY = {
    "absent",
    "reference_only",
    "scaffold",
    "partial",
    "substantively_informative",
    "uncertain",
}
METHOD_USE = {
    "exclude",
    "provenance_only",
    "uncertainty_context",
    "supplementary_candidate",
    "primary_candidate",
}
INFORMATION_GAIN = {"none", "minimal", "material"}
CONFIDENCE = {"low", "medium", "high"}


class ValidationError(RuntimeError):
    """Raised when a Task 04c output violates its contract."""


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"expected YAML mapping: {path}")
    return value


def git(repo: Path, *args: str, text: bool = True) -> Any:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=text,
    )
    if text:
        return result.stdout.rstrip("\n")
    return result.stdout


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValidationError(f"timestamp lacks timezone: {value}")
    return parsed.astimezone(UTC)


def approved_inventory() -> dict[str, dict[int, tuple[Path, dict[str, Any]]]]:
    inventory: dict[str, dict[int, tuple[Path, dict[str, Any]]]] = {}
    for fork in FORKS:
        inventory[fork] = {}
        for path in sorted((TASK04_ROOT / fork).glob("eip-*.yaml")):
            record = load_yaml(path)
            if record["review"]["status"] != "approved":
                continue
            if "execution" not in record["eip"]["layers"]:
                continue
            inventory[fork][int(record["eip"]["number"])] = (path, record)
    return inventory


def validate_repository_metadata() -> dict[str, dict[str, Any]]:
    record = load_yaml(TASK_ROOT / "outputs/repositories.yaml")
    if record.get("schema_version") != 1 or record.get("task_id") != TASK_ID:
        raise ValidationError("repository metadata identity mismatch")
    repositories = record.get("repositories", {})
    if set(repositories) != set(REPOSITORY_IDS):
        raise ValidationError("repository metadata inventory mismatch")
    for repository_id, metadata in repositories.items():
        repo = Path(metadata["local_path"])
        if not repo.is_dir():
            raise ValidationError(f"missing repository: {repo}")
        for field in ("current_head", "base_ref_head", "first_parent_root_commit"):
            sha = str(metadata[field])
            if len(sha) != 40:
                raise ValidationError(f"non-full SHA in {repository_id}.{field}")
            git(repo, "cat-file", "-e", f"{sha}^{{commit}}")
        if metadata["object_format"] != "sha1":
            raise ValidationError(f"unexpected object format for {repository_id}")
        if metadata["shallow"] or metadata["partial"]:
            raise ValidationError(f"incomplete clone recorded for {repository_id}")
        if metadata["missing_reachable_objects"]:
            raise ValidationError(f"missing reachable objects for {repository_id}")
        if not metadata["history_covers_required_cutoffs"]:
            raise ValidationError(f"history gap for {repository_id}")
    for event in record.get("migration_history", []):
        matching = [
            value
            for value in repositories.values()
            if value["repository"] == event["repository"]
        ]
        if len(matching) != 1:
            raise ValidationError(f"migration repository does not resolve: {event}")
        repo = Path(matching[0]["local_path"])
        git(repo, "cat-file", "-e", f'{event["commit"]}^{{commit}}')
    return repositories


def validate_blob(
    repo: Path,
    github: str,
    snapshot: str,
    cutoff: datetime,
    blob: dict[str, Any],
) -> None:
    path = blob["path"]
    if len(blob["commit"]) != 40 or blob["commit"] != snapshot:
        raise ValidationError(f"blob commit mismatch: {snapshot}:{path}")
    actual_blob = git(repo, "rev-parse", f"{snapshot}:{path}")
    if len(actual_blob) != 40 or actual_blob != blob["git_blob_sha"]:
        raise ValidationError(f"blob SHA mismatch: {snapshot}:{path}")
    content = git(repo, "cat-file", "blob", f"{snapshot}:{path}", text=False)
    if hashlib.sha256(content).hexdigest() != blob["content_sha256"]:
        raise ValidationError(f"content SHA-256 mismatch: {snapshot}:{path}")
    expected_url = f"{github}/blob/{snapshot}/{path}"
    if blob["immutable_url"] != expected_url:
        raise ValidationError(f"immutable URL mismatch: {snapshot}:{path}")
    changed = git(
        repo,
        "log",
        "-1",
        "--format=%H%x09%cI%x09%s",
        snapshot,
        "--",
        path,
    ).split("\t", 2)
    if len(changed) != 3:
        raise ValidationError(f"cannot recompute last change: {snapshot}:{path}")
    if changed[0] != blob["last_changed_commit"] or changed[1] != blob["last_changed_at"]:
        raise ValidationError(f"last-change provenance mismatch: {snapshot}:{path}")
    if parse_instant(changed[1]) > cutoff:
        raise ValidationError(f"cited blob first appears after cutoff: {snapshot}:{path}")


def validate_record(
    path: Path,
    fork: str,
    number: int,
    task04_path: Path,
    task04: dict[str, Any],
    repository_metadata: dict[str, dict[str, Any]],
) -> Counter[tuple[str, str]]:
    record = load_yaml(path)
    if record.get("schema_version") != 1 or record.get("task_id") != TASK_ID:
        raise ValidationError(f"identity mismatch: {path}")
    if record.get("fork_id") != fork or int(record["eip"]["number"]) != number:
        raise ValidationError(f"fork/EIP identity mismatch: {path}")
    if record["eip"]["title"] != task04["eip"]["title"]:
        raise ValidationError(f"title mismatch: {path}")
    inputs = record["inputs"]
    expected_task04 = task04_path.relative_to(REPO_ROOT).as_posix()
    if inputs["task04_record"] != expected_task04:
        raise ValidationError(f"Task 04 path mismatch: {path}")
    if inputs["task04_review_status"] != "approved":
        raise ValidationError(f"unapproved Task 04 input: {path}")
    if str(inputs["information_cutoff_at"]) != str(
        task04["selection"]["information_cutoff_at"]
    ):
        raise ValidationError(f"cutoff mismatch: {path}")
    cutoff = parse_instant(inputs["normalized_information_cutoff_at"])
    selected = task04["selection"]["selected_revision"]
    for field in ("commit", "git_blob_sha", "content_sha256"):
        if inputs["selected_eip_revision"][field] != selected[field]:
            raise ValidationError(f"selected EIP {field} mismatch: {path}")
    if set(record["repositories"]) != set(REPOSITORY_IDS):
        raise ValidationError(f"repository judgment inventory mismatch: {path}")
    counts: Counter[tuple[str, str]] = Counter()
    for repository_id in REPOSITORY_IDS:
        judgment = record["repositories"][repository_id]
        metadata = repository_metadata[repository_id]
        if judgment["repository"] != metadata["repository"]:
            raise ValidationError(f"repository identity mismatch: {path}")
        repo = Path(metadata["local_path"])
        snapshot = judgment["snapshot"]
        if snapshot["base_ref"] != metadata["base_ref"]:
            raise ValidationError(f"base ref mismatch: {path}")
        expected_commit = git(
            repo,
            "rev-list",
            "--first-parent",
            "-1",
            f"--before={inputs['normalized_information_cutoff_at']}",
            metadata["base_ref"],
        )
        if snapshot["commit"] != expected_commit or len(expected_commit) != 40:
            raise ValidationError(f"snapshot resolution mismatch: {path}/{repository_id}")
        committed_at = git(repo, "show", "-s", "--format=%cI", expected_commit)
        if snapshot["committed_at"] != committed_at:
            raise ValidationError(f"snapshot time mismatch: {path}/{repository_id}")
        if parse_instant(committed_at) > cutoff or not snapshot["at_or_before_cutoff"]:
            raise ValidationError(f"post-cutoff snapshot: {path}/{repository_id}")
        if snapshot["tree_sha"] != git(repo, "rev-parse", f"{expected_commit}^{{tree}}"):
            raise ValidationError(f"tree SHA mismatch: {path}/{repository_id}")
        maturity = judgment["maturity"]
        method_use = judgment["methodological_use"]
        if maturity not in MATURITY or method_use not in METHOD_USE:
            raise ValidationError(f"classification enum mismatch: {path}/{repository_id}")
        if judgment["information_gain"]["level"] not in INFORMATION_GAIN:
            raise ValidationError(f"information-gain enum mismatch: {path}/{repository_id}")
        if judgment["confidence"]["level"] not in CONFIDENCE:
            raise ValidationError(f"confidence enum mismatch: {path}/{repository_id}")
        binding = judgment.get("reference_spec_binding")
        if binding is not None:
            declared = binding["declared_git_blob_sha"]
            if len(declared) != 40:
                raise ValidationError(f"reference-spec blob is not full: {path}/{repository_id}")
            expected_match = declared == selected["git_blob_sha"]
            if binding["matches_task04_selected_blob"] != expected_match:
                raise ValidationError(f"reference-spec binding mismatch: {path}/{repository_id}")
            eips_repo = Path("/home/dtopz/code/github/EIPs")
            object_lines = [
                line
                for line in git(eips_repo, "rev-list", "--all", "--objects").splitlines()
                if line.startswith(f"{declared} ")
            ]
            if not any(
                line.split(" ", 1)[1] == binding["resolved_object_path"]
                for line in object_lines
            ):
                raise ValidationError(f"reference-spec object path mismatch: {path}/{repository_id}")
        blobs = judgment["relevant_blobs"]
        if len({blob["path"] for blob in blobs}) != len(blobs):
            raise ValidationError(f"duplicate blob path: {path}/{repository_id}")
        if judgment["publicly_present_by_cutoff"] != bool(blobs):
            raise ValidationError(f"availability/blob mismatch: {path}/{repository_id}")
        if maturity == "absent" and blobs:
            raise ValidationError(f"absent judgment cites blobs: {path}/{repository_id}")
        if maturity != "absent" and not blobs:
            raise ValidationError(f"positive judgment lacks blobs: {path}/{repository_id}")
        github = judgment["provenance"]["remote"]
        for blob in blobs:
            validate_blob(repo, github, expected_commit, cutoff, blob)
        counts[("maturity", maturity)] += 1
        counts[("methodological_use", method_use)] += 1
    expected_overall = (
        "supplementary_candidate"
        if any(
            value["methodological_use"] == "supplementary_candidate"
            for value in record["repositories"].values()
        )
        else "exclude"
    )
    if record["overall"]["recommended_use"] != expected_overall:
        raise ValidationError(f"overall use mismatch: {path}")
    return counts


def main() -> None:
    repositories = validate_repository_metadata()
    inventory = approved_inventory()
    expected_files = {
        fork: {f"eip-{number}.yaml" for number in records}
        for fork, records in inventory.items()
    }
    summary: dict[str, dict[str, Any]] = {}
    for fork in FORKS:
        output_dir = TASK_ROOT / f"outputs/fork-eips/{fork}"
        actual_files = {path.name for path in output_dir.glob("eip-*.yaml")}
        if actual_files != expected_files[fork]:
            raise ValidationError(
                f"inventory mismatch for {fork}: missing={sorted(expected_files[fork] - actual_files)}, extra={sorted(actual_files - expected_files[fork])}"
            )
        counts: Counter[tuple[str, str]] = Counter()
        for number, (task04_path, task04) in sorted(inventory[fork].items()):
            counts.update(
                validate_record(
                    output_dir / f"eip-{number}.yaml",
                    fork,
                    number,
                    task04_path,
                    task04,
                    repositories,
                )
            )
        fork_summary = load_yaml(TASK_ROOT / f"outputs/forks/{fork}.yaml")
        expected_maturity = {
            value: counts[("maturity", value)] for value in sorted(MATURITY)
        }
        expected_use = {
            value: counts[("methodological_use", value)]
            for value in sorted(METHOD_USE)
        }
        if fork_summary["counts"]["maturity"] != expected_maturity:
            raise ValidationError(f"maturity summary mismatch: {fork}")
        if fork_summary["counts"]["methodological_use"] != expected_use:
            raise ValidationError(f"methodological-use summary mismatch: {fork}")
        if fork_summary["eip_count"] != len(inventory[fork]):
            raise ValidationError(f"EIP count mismatch: {fork}")
        if fork_summary["repository_eip_judgment_count"] != 2 * len(inventory[fork]):
            raise ValidationError(f"judgment count mismatch: {fork}")
        summary[fork] = {
            "eips": len(inventory[fork]),
            "repository_eip_judgments": 2 * len(inventory[fork]),
            "maturity": expected_maturity,
            "methodological_use": expected_use,
        }
    print(yaml.safe_dump({"task_id": TASK_ID, "forks": summary}, sort_keys=False))


if __name__ == "__main__":
    main()
