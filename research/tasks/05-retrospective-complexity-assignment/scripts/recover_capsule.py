#!/usr/bin/env python3
"""Recover, preserve, normalize if necessary, and collect a stranded capsule output."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from mark_complete import CompletionError, checklist_path, tick
from validate_output import (
    TASK_ROOT,
    ValidationError,
    package_paths,
    validate,
)


NORMALIZATION_ID = "task05_first_run_schema_normalization_v1"
FREE_TEXT_KEYS = {
    "attestation",
    "exceptional_score_justification",
    "historical_scope_summary",
    "locator",
    "rationale",
    "summary",
    "uncertainty_note",
}


class RecoveryError(RuntimeError):
    """Raised when a stranded capsule cannot be recovered safely."""


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RecoveryError(f"Expected a YAML mapping: {path}")
    return data


def yaml_bytes(data: dict[str, Any]) -> bytes:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    ).encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repair_plain_free_text(text: str) -> tuple[str, int]:
    repaired: list[str] = []
    count = 0
    pattern = re.compile(r"^(?P<prefix>\s*(?P<key>[a-z_]+):\s+)(?P<value>.*)$")
    for line in text.splitlines(keepends=True):
        content = line.removesuffix("\n")
        newline = "\n" if line.endswith("\n") else ""
        match = pattern.match(content)
        if not match or match.group("key") not in FREE_TEXT_KEYS:
            repaired.append(line)
            continue
        value = match.group("value")
        if (
            value in {"null", ">-", "|", "|-", "|+"}
            or value.startswith("'")
            or value.startswith('"')
        ):
            repaired.append(line)
            continue
        repaired.append(match.group("prefix") + json.dumps(value, ensure_ascii=False) + newline)
        count += 1
    return "".join(repaired), count


def write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(descriptor, "wb") as destination:
            descriptor = None
            destination.write(payload)
            destination.flush()
            os.fsync(destination.fileno())
    except FileExistsError as error:
        raise RecoveryError(f"Refusing to overwrite an existing file: {path}") from error
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if path.exists():
            path.unlink()
        raise


def package_source(value: str, expected_sources: list[str]) -> str | None:
    if value in expected_sources:
        return value
    if value.startswith("package/") and value.removeprefix("package/") in expected_sources:
        return value.removeprefix("package/")
    return None


def normalize(
    result: dict[str, Any],
    *,
    expected_sources: list[str],
    expected_rubric_source: dict[str, Any],
    raw_path: Path,
    raw_sha256: str,
    syntax_repairs: int = 0,
) -> dict[str, Any]:
    normalized = copy.deepcopy(result)
    provenance = normalized.setdefault("provenance", {})
    rubric_source_restored = False
    actual_rubric_source = provenance.get("rubric_source")
    if actual_rubric_source != expected_rubric_source:
        if not isinstance(actual_rubric_source, dict):
            raise RecoveryError("Legacy rubric_source is not a mapping")
        differing_keys = {
            key
            for key in set(actual_rubric_source) | set(expected_rubric_source)
            if actual_rubric_source.get(key) != expected_rubric_source.get(key)
        }
        if differing_keys != {"immutable_url"}:
            raise RecoveryError(
                "Refusing to restore rubric_source because fields other than immutable_url differ"
            )
        provenance["rubric_source"] = copy.deepcopy(expected_rubric_source)
        rubric_source_restored = True
    original_sources = provenance.get("sources_consulted")
    if not isinstance(original_sources, list) or not all(
        isinstance(item, str) for item in original_sources
    ):
        raise RecoveryError("Legacy sources_consulted is not a string list")

    seen_assessment_sources = {
        mapped
        for item in original_sources
        if (mapped := package_source(item, expected_sources)) is not None
    }
    if seen_assessment_sources != set(expected_sources):
        raise RecoveryError(
            "Legacy output did not consult exactly the sealed assessment sources"
        )
    sources_split = original_sources != expected_sources
    provenance["sources_consulted"] = expected_sources
    operational_from_sources = [
        item
        for item in original_sources
        if package_source(item, expected_sources) is None
    ]
    existing_operational = provenance.get("operational_files_read")
    if operational_from_sources:
        provenance["operational_files_read"] = operational_from_sources
    elif isinstance(existing_operational, list):
        provenance["operational_files_read"] = existing_operational
    else:
        provenance["operational_files_read"] = []

    evidence_converted = False
    for index, criterion in enumerate(normalized.get("criteria", [])):
        evidence = criterion.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise RecoveryError(f"criteria[{index}].evidence is missing")
        converted: list[dict[str, str]] = []
        for item in evidence:
            if isinstance(item, dict):
                converted.append(item)
                continue
            evidence_converted = True
            if not isinstance(item, str) or ":" not in item:
                raise RecoveryError(
                    f"criteria[{index}].evidence contains an unrecognized legacy value"
                )
            raw_source, locator = item.split(":", 1)
            source = package_source(raw_source.strip(), expected_sources)
            if source is None:
                raise RecoveryError(
                    f"criteria[{index}].evidence uses a non-package source: {raw_source}"
                )
            converted.append(
                {
                    "source": source,
                    "locator": locator.strip(),
                    "summary": criterion["rationale"],
                }
            )
        criterion["evidence"] = converted

        if criterion.get("id") == "cross_eip_interactions":
            interactions = criterion.get("interacting_eips")
            if not isinstance(interactions, list):
                raise RecoveryError("cross_eip_interactions.interacting_eips is not a list")
            normalized_interactions: list[int] = []
            for item in interactions:
                if isinstance(item, int) and not isinstance(item, bool):
                    normalized_interactions.append(item)
                    continue
                if isinstance(item, str) and (
                    match := re.fullmatch(r"EIP-(\d+)", item.strip(), re.IGNORECASE)
                ):
                    normalized_interactions.append(int(match.group(1)))
                    continue
                raise RecoveryError(f"Unrecognized interacting EIP value: {item!r}")
            criterion["interacting_eips"] = normalized_interactions
            unidentified = criterion.get("unidentified_interactions", [])
            if not isinstance(unidentified, list):
                raise RecoveryError("unidentified_interactions is not a list")
            if criterion.get("score", 0) > 0 and not normalized_interactions and not unidentified:
                criterion["unidentified_interactions"] = [
                    "The sealed proposal describes an interacting proposal but does not provide its EIP number."
                ]

    provenance["assessor_raw_output"] = {
        "path": raw_path.relative_to(TASK_ROOT).as_posix(),
        "content_sha256": raw_sha256,
    }
    changes: list[str] = []
    if syntax_repairs:
        changes.append(
            f"quoted {syntax_repairs} unsafe plain YAML free-text scalars"
        )
    if rubric_source_restored:
        changes.append(
            "restored the rubric immutable URL from the capsule output template"
        )
    if sources_split:
        changes.append("split assessment sources from operational files")
    if evidence_converted:
        changes.append(
            "expanded scalar evidence locators into source/locator/summary mappings"
        )
    if any(
        isinstance(item, str)
        for criterion in result.get("criteria", [])
        if criterion.get("id") == "cross_eip_interactions"
        for item in criterion.get("interacting_eips", [])
    ):
        changes.append("normalized EIP-prefixed interaction identifiers to integers")
    if any(
        criterion.get("id") == "cross_eip_interactions"
        and criterion.get("score", 0) > 0
        and not criterion.get("interacting_eips")
        for criterion in result.get("criteria", [])
    ):
        changes.append("represented an unnumbered historical interaction explicitly")
    provenance["postprocessing"] = [
        {
            "id": NORMALIZATION_ID,
            "applied_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "semantic_scores_changed": False,
            "changes": changes,
        }
    ]
    return normalized


def recover(fork_id: str, number: int, capsule: Path) -> Path:
    capsule_output = capsule.resolve() / "assessment.yaml"
    if not capsule_output.is_file():
        raise RecoveryError(f"Capsule output is missing: {capsule_output}")
    package, canonical_output, _, _ = package_paths(fork_id, number)
    manifest = load_yaml(package / "manifest.yaml")
    template = load_yaml(package / "output-template.yaml")
    expected_sources = manifest.get("assessment_source_files")
    if not isinstance(expected_sources, list) or not expected_sources:
        raise RecoveryError("Canonical package has no assessment source allowlist")
    expected_rubric_source = template.get("provenance", {}).get("rubric_source")
    if not isinstance(expected_rubric_source, dict):
        raise RecoveryError("Canonical output template has no rubric_source mapping")

    raw_payload = capsule_output.read_bytes()
    raw_path = (
        TASK_ROOT
        / "outputs"
        / "raw"
        / "fork-eips"
        / fork_id
        / f"eip-{number}.yaml"
    )
    syntax_repairs = 0
    try:
        parsed = load_yaml(capsule_output)
    except yaml.YAMLError:
        repaired_text, syntax_repairs = repair_plain_free_text(
            raw_payload.decode("utf-8")
        )
        try:
            parsed = yaml.safe_load(repaired_text)
        except yaml.YAMLError as error:
            raise RecoveryError(
                "The conservative plain-scalar repair did not produce valid YAML"
            ) from error
        if not isinstance(parsed, dict):
            raise RecoveryError("Syntax-repaired output is not a YAML mapping")
    write_exclusive(raw_path, raw_payload)
    result = normalize(
        parsed,
        expected_sources=expected_sources,
        expected_rubric_source=expected_rubric_source,
        raw_path=raw_path,
        raw_sha256=sha256(raw_payload),
        syntax_repairs=syntax_repairs,
    )
    normalized_path = capsule.resolve() / "assessment.normalized.yaml"
    normalized_payload = yaml_bytes(result)
    write_exclusive(normalized_path, normalized_payload)
    validate(fork_id, number, output_override=normalized_path)
    write_exclusive(canonical_output, normalized_payload)
    validate(fork_id, number)
    tick(checklist_path(fork_id), number)
    print(f"preserved raw assessor output: {raw_path}")
    print(f"collected normalized assessment: {canonical_output}")
    return canonical_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fork", required=True)
    parser.add_argument("--eip", required=True, type=int)
    parser.add_argument("--capsule", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    recover(args.fork, args.eip, args.capsule)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RecoveryError, ValidationError, CompletionError) as error:
        raise SystemExit(f"recovery error: {error}") from error
