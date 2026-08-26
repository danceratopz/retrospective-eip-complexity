#!/usr/bin/env python3
"""Recover a structurally repairable Task 08 capsule without changing scores."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

from engine_adapter import TASK_ROOT, load_engine_module
from validate_assessment import NAMESPACE, ValidationError, package_paths, validate


engine = load_engine_module("recover_capsule")
engine.TASK_ROOT = TASK_ROOT
engine.NORMALIZATION_ID = "task08_structural_output_normalization_v1"
engine.FREE_TEXT_KEYS.add("snapshot_scope_summary")


def repair_unsafe_list_free_text(text: str) -> tuple[str, int]:
    """Quote a list scalar whose opening quote covers only its first phrase."""
    repaired: list[str] = []
    count = 0
    pattern = re.compile(r"^(?P<prefix>\s*-\s+)(?P<value>[\"'].*)$")
    for line in text.splitlines(keepends=True):
        content = line.removesuffix("\n")
        newline = "\n" if line.endswith("\n") else ""
        match = pattern.match(content)
        if not match:
            repaired.append(line)
            continue
        value = match.group("value")
        quote = value[0]
        if value.endswith(quote):
            repaired.append(line)
            continue
        repaired.append(
            match.group("prefix") + json.dumps(value, ensure_ascii=False) + newline
        )
        count += 1
    return "".join(repaired), count


def recover(number: int, capsule: Path) -> Path:
    capsule_output = capsule.resolve() / "assessment.yaml"
    if not capsule_output.is_file():
        raise engine.RecoveryError(f"Capsule output is missing: {capsule_output}")
    package, canonical_output, _, _ = package_paths("hegota", number)
    manifest = engine.load_yaml(package / "manifest.yaml")
    template = engine.load_yaml(package / "output-template.yaml")
    expected_sources = manifest.get("assessment_source_files")
    if not isinstance(expected_sources, list) or not expected_sources:
        raise engine.RecoveryError("Canonical package has no source allowlist")
    expected_rubric_source = template.get("provenance", {}).get("rubric_source")
    if not isinstance(expected_rubric_source, dict):
        raise engine.RecoveryError("Canonical template has no rubric_source mapping")

    raw_payload = capsule_output.read_bytes()
    raw_path = TASK_ROOT / "outputs" / "raw" / NAMESPACE / f"eip-{number}.yaml"
    syntax_repairs = 0
    try:
        parsed = engine.load_yaml(capsule_output)
    except yaml.YAMLError:
        repaired_text, mapping_repairs = engine.repair_plain_free_text(
            raw_payload.decode("utf-8")
        )
        repaired_text, list_repairs = repair_unsafe_list_free_text(repaired_text)
        syntax_repairs = mapping_repairs + list_repairs
        try:
            parsed = yaml.safe_load(repaired_text)
        except yaml.YAMLError as error:
            raise engine.RecoveryError(
                "Conservative plain-scalar repair did not produce valid YAML"
            ) from error
        if not isinstance(parsed, dict):
            raise engine.RecoveryError("Syntax-repaired output is not a YAML mapping")
    engine.write_exclusive(raw_path, raw_payload)
    normalized = engine.normalize(
        parsed,
        expected_sources=expected_sources,
        expected_rubric_source=expected_rubric_source,
        raw_path=raw_path,
        raw_sha256=engine.sha256(raw_payload),
        syntax_repairs=syntax_repairs,
    )
    normalized_path = capsule.resolve() / "assessment.normalized.yaml"
    payload = engine.yaml_bytes(normalized)
    engine.write_exclusive(normalized_path, payload)
    validate("hegota", number, output_override=normalized_path)
    engine.write_exclusive(canonical_output, payload)
    validate("hegota", number)
    print(f"preserved raw assessor output: {raw_path}")
    print(f"collected normalized assessment: {canonical_output}")
    return canonical_output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eip", required=True, type=int)
    parser.add_argument("--capsule", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    recover(args.eip, args.capsule)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (engine.RecoveryError, ValidationError) as error:
        raise SystemExit(f"recovery error: {error}") from error
