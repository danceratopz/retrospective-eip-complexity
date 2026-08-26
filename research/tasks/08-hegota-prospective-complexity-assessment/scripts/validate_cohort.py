#!/usr/bin/env python3
"""Validate the frozen Hegotá PFI cohort against its exact EIPs snapshot."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
DEFAULT_MANIFEST = TASK_ROOT / "inputs" / "hegota-pfi-2026-08-26.yaml"
ITEM_RE = re.compile(
    r"^\* \[EIP-(?P<label>\d+)\]\(\./eip-(?P<path>\d+)\.md\): "
    r"(?P<title>.+)$"
)


class CohortError(RuntimeError):
    """Raised when the frozen cohort disagrees with its pinned source."""


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CohortError(f"Expected a YAML mapping: {path}")
    return data


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        error = result.stderr.decode(errors="replace").strip()
        raise CohortError(f"git {' '.join(args)} failed in {repo}: {error}")
    return result.stdout


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CohortError(f"Timestamp has no UTC offset: {value}")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def frontmatter(data: bytes, path: str) -> dict[str, Any]:
    text = data.decode("utf-8")
    if not text.startswith("---\n"):
        raise CohortError(f"Missing YAML frontmatter: {path}")
    boundary = text.find("\n---\n", 4)
    if boundary < 0:
        raise CohortError(f"Unterminated YAML frontmatter: {path}")
    parsed = yaml.safe_load(text[4:boundary])
    if not isinstance(parsed, dict):
        raise CohortError(f"Invalid YAML frontmatter: {path}")
    return parsed


def section_items(text: str, heading: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    expected_heading = f"### {heading}"
    try:
        start = lines.index(expected_heading) + 1
    except ValueError as exc:
        raise CohortError(f"Missing EIP-8081 section: {expected_heading}") from exc

    items: list[tuple[int, str]] = []
    for line in lines[start:]:
        if line.startswith("### "):
            break
        if not line.strip():
            continue
        match = ITEM_RE.fullmatch(line)
        if match is None:
            raise CohortError(f"Unexpected line in {expected_heading}: {line!r}")
        label_number = int(match.group("label"))
        path_number = int(match.group("path"))
        if label_number != path_number:
            raise CohortError(
                f"EIP label/path mismatch in {expected_heading}: {line!r}"
            )
        items.append((label_number, match.group("title")))
    return items


def require_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise CohortError(f"{label}: expected {expected!r}, found {actual!r}")


def validate(manifest_path: Path, eips_repo: Path) -> tuple[str, int]:
    manifest = load_yaml(manifest_path)
    require_equal("schema_version", manifest.get("schema_version"), 1)
    require_equal(
        "task_id",
        manifest.get("task_id"),
        "08-hegota-prospective-complexity-assessment",
    )

    source = manifest.get("source")
    selection = manifest.get("selection")
    inventory = manifest.get("inventory")
    if not isinstance(source, dict):
        raise CohortError("source must be a mapping")
    if not isinstance(selection, dict):
        raise CohortError("selection must be a mapping")
    if not isinstance(inventory, list):
        raise CohortError("inventory must be a list")

    commit = str(source["repository_commit"])
    path = str(source["path"])
    git(eips_repo, "rev-parse", "--verify", f"{commit}^{{commit}}")

    parent = git(eips_repo, "rev-parse", f"{commit}^").decode().strip()
    require_equal("source.parent_commit", parent, source["parent_commit"])
    committed_at = git(eips_repo, "show", "-s", "--format=%cI", commit).decode().strip()
    require_equal(
        "source.committed_at",
        normalize_timestamp(committed_at),
        source["committed_at"],
    )
    subject = git(eips_repo, "show", "-s", "--format=%s", commit).decode().strip()
    require_equal("source.commit_subject", subject, source["commit_subject"])

    meta_bytes = git(eips_repo, "show", f"{commit}:{path}")
    blob = git(eips_repo, "rev-parse", f"{commit}:{path}").decode().strip()
    require_equal("source.git_blob_sha", blob, source["git_blob_sha"])
    require_equal("source.content_sha256", sha256(meta_bytes), source["content_sha256"])

    meta = frontmatter(meta_bytes, path)
    require_equal("EIP-8081 frontmatter eip", meta.get("eip"), 8081)
    require_equal("EIP-8081 frontmatter title", meta.get("title"), "Hardfork Meta - Hegotá")
    require_equal("EIP-8081 frontmatter type", meta.get("type"), "Meta")

    text = meta_bytes.decode("utf-8")
    require_equal("selection.section", selection.get("section"), "Proposed for Inclusion")
    source_pfi = section_items(text, "Proposed for Inclusion")
    expected_pfi = [
        (int(entry["eip"]), str(entry["listed_title"]))
        for entry in inventory
        if isinstance(entry, dict)
    ]
    if len(expected_pfi) != len(inventory):
        raise CohortError("Every inventory entry must be a mapping")
    require_equal("ordered PFI inventory", source_pfi, expected_pfi)
    require_equal("PFI count", len(source_pfi), selection["expected_count"])
    if len({number for number, _ in source_pfi}) != len(source_pfi):
        raise CohortError("PFI inventory contains duplicate EIP numbers")

    excluded = selection.get("excluded_sections")
    if not isinstance(excluded, dict):
        raise CohortError("selection.excluded_sections must be a mapping")
    scheduled = [number for number, _ in section_items(text, "EIPs Scheduled for Inclusion")]
    considered = [number for number, _ in section_items(text, "Considered for Inclusion")]
    require_equal(
        "scheduled-for-inclusion exclusion",
        scheduled,
        excluded.get("scheduled_for_inclusion"),
    )
    require_equal(
        "considered-for-inclusion exclusion",
        considered,
        excluded.get("considered_for_inclusion"),
    )
    selected_numbers = {number for number, _ in source_pfi}
    if selected_numbers.intersection(scheduled + considered):
        raise CohortError("PFI cohort overlaps an explicitly excluded section")

    for index, entry in enumerate(inventory, start=1):
        if not isinstance(entry, dict):
            raise CohortError(f"Inventory entry {index} is not a mapping")
        number = int(entry["eip"])
        expected_path = f"EIPS/eip-{number}.md"
        require_equal(f"EIP-{number} path", entry.get("path"), expected_path)
        eip_bytes = git(eips_repo, "show", f"{commit}:{expected_path}")
        fields = frontmatter(eip_bytes, expected_path)
        require_equal(f"EIP-{number} frontmatter eip", fields.get("eip"), number)
        require_equal(
            f"EIP-{number} canonical title",
            fields.get("title"),
            entry.get("canonical_title"),
        )
        require_equal(
            f"EIP-{number} type", fields.get("type"), entry.get("eip_type")
        )
        require_equal(
            f"EIP-{number} category", fields.get("category"), entry.get("category")
        )

    return str(manifest["snapshot_id"]), len(inventory)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Frozen Task 08 cohort manifest",
    )
    parser.add_argument(
        "--eips-repo",
        type=Path,
        default=REPO_ROOT.parent / "EIPs",
        help="Local complete ethereum/EIPs clone",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot_id, count = validate(args.manifest.resolve(), args.eips_repo.resolve())
    print(f"Validated {count} Hegotá PFI entries for {snapshot_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
