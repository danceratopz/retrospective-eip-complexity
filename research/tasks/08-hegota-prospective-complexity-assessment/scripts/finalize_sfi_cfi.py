#!/usr/bin/env python3
"""Freeze the SFI/CFI results and render extension and combined summaries."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from engine_adapter import REPO_ROOT, TASK_ROOT, package_engine
from validate_sfi_cfi_assessment import OUTPUT_ROOT, RAW_ROOT, validate
from validate_sfi_cfi_packages import PACKAGE_FREEZE, validate_inventory


EXTENSION_ROOT = TASK_ROOT / "extensions" / "sfi-cfi-2026-08-26"
REVIEW_PATH = EXTENSION_ROOT / "outputs" / "cohort-review.yaml"
ASSESSMENT_FREEZE = EXTENSION_ROOT / "outputs" / "assessment-manifest.yaml"
SUMMARY_YAML = EXTENSION_ROOT / "outputs" / "summary.yaml"
SUMMARY_MD = EXTENSION_ROOT / "outputs" / "summary.md"
COMBINED_YAML = TASK_ROOT / "outputs" / "summary-all-candidates.yaml"
COMBINED_MD = TASK_ROOT / "outputs" / "summary-all-candidates.md"
VALIDATION_REPORT = EXTENSION_ROOT / "outputs" / "validation-report.yaml"
ORIGINAL_PACKAGE_FREEZE = TASK_ROOT / "outputs" / "package-manifest.yaml"
ORIGINAL_ASSESSMENT_FREEZE = TASK_ROOT / "outputs" / "assessment-manifest.yaml"
ORIGINAL_SUMMARY_YAML = TASK_ROOT / "outputs" / "summary.yaml"
ORIGINAL_SUMMARY_MD = TASK_ROOT / "outputs" / "summary.md"
ORIGINAL_HASHES = {
    ORIGINAL_PACKAGE_FREEZE: "5e7c447d725a7cc8779bd363b0075450ac629dc01306a5328136d8d7084c0468",
    ORIGINAL_ASSESSMENT_FREEZE: "4c6bd4cc5d27e1a19783ea58c59099b35f1dce7d296218d5ab6c0252a6265828",
    ORIGINAL_SUMMARY_YAML: "e604abb081fa3ef515b9413f218a0e72dc906400204413dc3af7865db1968b70",
    ORIGINAL_SUMMARY_MD: "a04b8eb0ddf07cf398fe0356fd059c13afff7399bcc1e3bbd54102aa58aaaa92",
}


class FinalizationError(RuntimeError):
    """Raised when an original or extension freeze invariant fails."""


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def load(path: Path) -> dict[str, Any]:
    return package_engine.load_yaml(path)


def verify_original() -> None:
    for path, expected in ORIGINAL_HASHES.items():
        if package_engine.file_sha256(path) != expected:
            raise FinalizationError(f"Original Task 08 artifact changed: {rel(path)}")
    manifest = load(ORIGINAL_ASSESSMENT_FREEZE)
    if manifest.get("assessment_count") != 37:
        raise FinalizationError("Original Task 08 assessment count changed")
    for record in manifest["assessments"]:
        path = REPO_ROOT / record["assessment_path"]
        if package_engine.file_sha256(path) != record["assessment_sha256"]:
            raise FinalizationError(f"Original assessment changed: {rel(path)}")
        raw = record.get("raw_output")
        if raw and package_engine.file_sha256(REPO_ROOT / raw["path"]) != raw["content_sha256"]:
            raise FinalizationError(f"Original raw output changed for EIP-{record['eip']}")


def review_entries() -> list[dict[str, Any]]:
    review = load(REVIEW_PATH)
    if review.get("review_gate", {}).get("status") != "approved":
        raise FinalizationError("SFI/CFI review is not approved")
    return review["entries"]


def assessment_inventory() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for entry in review_entries():
        number = int(entry["eip"])
        output = OUTPUT_ROOT / f"eip-{number}.yaml"
        validate("hegota", number)
        raw = RAW_ROOT / f"eip-{number}.yaml"
        records.append(
            {
                "eip": number,
                "snapshot_status": entry["snapshot_status"],
                "assessment_path": rel(output),
                "assessment_sha256": package_engine.file_sha256(output),
                "raw_output": (
                    {"path": rel(raw), "content_sha256": package_engine.file_sha256(raw)}
                    if raw.is_file()
                    else None
                ),
            }
        )
    actual = sorted(int(path.stem.removeprefix("eip-")) for path in OUTPUT_ROOT.glob("eip-*.yaml"))
    if actual != [7805, 8141]:
        raise FinalizationError(f"Extension assessment inventory mismatch: {actual}")
    return {
        "schema_version": 1,
        "task_id": "08-hegota-prospective-complexity-assessment-result-freeze",
        "extension_id": "sfi-cfi-2026-08-26",
        "snapshot_id": "hegota-sfi-cfi-2026-08-26-ac450a4",
        "publication_label": "Hegotá SFI'd/CFI'd EIPs at the time of the 2026-08-26 snapshot",
        "cohort_review": {"path": rel(REVIEW_PATH), "content_sha256": package_engine.file_sha256(REVIEW_PATH)},
        "package_freeze": {"path": rel(PACKAGE_FREEZE), "content_sha256": package_engine.file_sha256(PACKAGE_FREEZE)},
        "parent_assessment_freeze": {"path": rel(ORIGINAL_ASSESSMENT_FREEZE), "content_sha256": ORIGINAL_HASHES[ORIGINAL_ASSESSMENT_FREEZE]},
        "assessment_count": len(records),
        "raw_output_count": sum(item["raw_output"] is not None for item in records),
        "assessments": records,
    }


def scored_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in review_entries():
        number = int(entry["eip"])
        assessment = load(OUTPUT_ROOT / f"eip-{number}.yaml")
        rows.append(
            {
                "eip": number,
                "title": entry["canonical_title"],
                "snapshot_status": entry["snapshot_status"],
                "affected_layers": entry["affected_layers"],
                "score": assessment["totals"]["primary_score"],
                "tier": assessment["totals"]["complexity_tier"],
                "confidence": assessment["overall_confidence"],
                "under_specification": assessment["under_specification"]["present"],
            }
        )
    return rows


def distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tiers = Counter(item["tier"] for item in rows)
    confidence = Counter(item["confidence"] for item in rows)
    return {
        "tiers": {name: tiers.get(name, 0) for name in ("low", "medium", "high")},
        "confidence": {name: confidence.get(name, 0) for name in ("low", "medium", "high")},
        "under_specification": {
            "present": sum(item["under_specification"] for item in rows),
            "absent": sum(not item["under_specification"] for item in rows),
        },
    }


def extension_summary() -> dict[str, Any]:
    rows = scored_rows()
    return {
        "schema_version": 1,
        "task_id": "08-hegota-prospective-complexity-assessment-extension-summary",
        "extension_id": "sfi-cfi-2026-08-26",
        "publication_label": "Hegotá SFI'd/CFI'd EIPs at the time of the 2026-08-26 snapshot",
        "snapshot": {
            "snapshot_id": "hegota-sfi-cfi-2026-08-26-ac450a4",
            "parent_snapshot_id": "hegota-pfi-2026-08-26-ac450a4",
            "captured_on": "2026-08-26",
            "repository": "ethereum/EIPs",
            "commit": "ac450a4ab2f37387385ee9c54b62f518d97e6cc9",
            "information_cutoff_at": "2026-08-25T11:56:58Z",
        },
        "population": {"entries": 2, "sfi_entries": 1, "cfi_entries": 1, "scored_el_rubric": 2},
        "el_rubric_total": {"score_sum": sum(item["score"] for item in rows), "scored_denominator": 2},
        "distributions": distribution(rows),
        "scored_eips": rows,
        "caveats": [
            "These are Hegotá SFI'd/CFI'd EIPs at the time of the 2026-08-26 snapshot, not members of the original PFI cohort.",
            "EIP-7805 is cross-layer; its score covers only execution-layer and execution-client networking complexity.",
            "Both assessments use the original frozen information cutoff, rubric, model settings, and isolation procedure.",
        ],
    }


def combined_summary(extension: dict[str, Any]) -> dict[str, Any]:
    original = load(ORIGINAL_SUMMARY_YAML)
    original_scored = [{**item, "snapshot_status": "PFI"} for item in original["scored_eips"]]
    original_na = [{**item, "snapshot_status": "PFI"} for item in original["not_applicable_eips"]]
    rows = sorted([*original_scored, *extension["scored_eips"]], key=lambda item: item["eip"])
    not_applicable = sorted(original_na, key=lambda item: item["eip"])
    extension_total = extension["el_rubric_total"]["score_sum"]
    return {
        "schema_version": 1,
        "task_id": "08-hegota-prospective-complexity-assessment-all-candidates-summary",
        "publication_label": "Hegotá candidates at the 2026-08-26 snapshot",
        "extension_publication_label": extension["publication_label"],
        "snapshot": {
            "snapshot_id": "hegota-candidates-2026-08-26-ac450a4",
            "original_pfi_snapshot_id": "hegota-pfi-2026-08-26-ac450a4",
            "sfi_cfi_extension_snapshot_id": extension["snapshot"]["snapshot_id"],
            "captured_on": "2026-08-26",
            "repository": "ethereum/EIPs",
            "commit": "ac450a4ab2f37387385ee9c54b62f518d97e6cc9",
            "information_cutoff_at": "2026-08-25T11:56:58Z",
        },
        "population": {
            "meta_eip_listed_entries": 46,
            "pfi_entries": 44,
            "sfi_entries": 1,
            "cfi_entries": 1,
            "scored_el_rubric": 39,
            "not_applicable_total": 7,
            "consensus_only_not_applicable": 5,
            "explicit_owner_exclusions": 2,
        },
        "el_rubric_totals": {
            "original_pfi": {"score_sum": 776, "scored_denominator": 37},
            "sfi_cfi_extension": {"score_sum": extension_total, "scored_denominator": 2},
            "all_candidates": {"score_sum": 776 + extension_total, "scored_denominator": 39},
        },
        "distributions": distribution(rows),
        "scored_eips": rows,
        "not_applicable_eips": not_applicable,
        "source_freezes": {
            "original_assessments": {"path": rel(ORIGINAL_ASSESSMENT_FREEZE), "content_sha256": ORIGINAL_HASHES[ORIGINAL_ASSESSMENT_FREEZE]},
            "extension_assessments": {"path": rel(ASSESSMENT_FREEZE), "content_sha256": package_engine.file_sha256(ASSESSMENT_FREEZE)},
        },
        "caveats": [
            "The original PFI-only result remains 776 across 37 scored EIPs and is not rewritten by this combined view.",
            "EIP-7805 was SFI and EIP-8141 was CFI, rather than PFI, at the frozen 2026-08-26 snapshot.",
            "Scores cover execution-layer and execution-client networking surfaces only; EIP-7805 consensus-layer work is not scored.",
            "Proposal splitting and cross-EIP interactions can overlap complexity, so score sums are not additive implementation-effort estimates.",
            "No post-snapshot proposal text, implementation evidence, outcomes, or later fork decisions were available to assessors.",
        ],
    }


def extension_markdown(summary: dict[str, Any]) -> bytes:
    lines = [
        "# Hegotá SFI/CFI prospective execution-layer complexity",
        "",
        f"**{summary['publication_label']}**.",
        "",
        f"EL-rubric subtotal: **{summary['el_rubric_total']['score_sum']} across 2 scored EIPs**.",
        "",
        "| EIP | Proposal | Snapshot status | Layers | Score | Tier | Confidence | Under-specified |",
        "|---:|---|---|---|---:|---|---|---|",
    ]
    for item in summary["scored_eips"]:
        lines.append(
            f"| EIP-{item['eip']} | {item['title']} | {item['snapshot_status']} | "
            f"{', '.join(item['affected_layers'])} | {item['score']} | {item['tier']} | "
            f"{item['confidence']} | {'yes' if item['under_specification'] else 'no'} |"
        )
    lines.extend(["", "## Caveats", "", *[f"- {item}" for item in summary["caveats"]], ""])
    return "\n".join(lines).encode()


def combined_markdown(summary: dict[str, Any]) -> bytes:
    totals = summary["el_rubric_totals"]
    lines = [
        "# Hegotá candidate complexity at the 2026-08-26 snapshot",
        "",
        f"Original PFI result: **{totals['original_pfi']['score_sum']} across 37 scored PFI EIPs**. "
        f"SFI/CFI extension: **{totals['sfi_cfi_extension']['score_sum']} across 2 scored EIPs**. "
        f"Combined visibility view: **{totals['all_candidates']['score_sum']} across 39 scored EIPs**.",
        "",
        "EIP-7805 and EIP-8141 are Hegotá SFI'd/CFI'd EIPs at the time of the 2026-08-26 snapshot; the status column distinguishes them from the original PFI cohort.",
        "",
        "## Scored execution-layer surfaces",
        "",
        "| EIP | Proposal | Snapshot status | Layers | Score | Tier | Confidence | Under-specified |",
        "|---:|---|---|---|---:|---|---|---|",
    ]
    for item in summary["scored_eips"]:
        lines.append(
            f"| EIP-{item['eip']} | {item['title']} | {item['snapshot_status']} | "
            f"{', '.join(item['affected_layers'])} | {item['score']} | {item['tier']} | "
            f"{item['confidence']} | {'yes' if item['under_specification'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Not applicable to the EL rubric",
            "",
            "| EIP | Proposal | Snapshot status | Basis | Rationale |",
            "|---:|---|---|---|---|",
        ]
    )
    for item in summary["not_applicable_eips"]:
        lines.append(
            f"| EIP-{item['eip']} | {item['title']} | {item['snapshot_status']} | "
            f"{item['exclusion_kind'].replace('_', ' ')} | {item['rationale']} |"
        )
    lines.extend(["", "## Caveats", "", *[f"- {item}" for item in summary["caveats"]], ""])
    return "\n".join(lines).encode()


def freeze() -> None:
    verify_original()
    validate_inventory()
    package_engine.write_bytes(ASSESSMENT_FREEZE, package_engine.yaml_bytes(assessment_inventory()))
    print(f"froze extension assessments: {ASSESSMENT_FREEZE}")


def summarize() -> None:
    verify_original()
    frozen = package_engine.yaml_bytes(assessment_inventory())
    if not ASSESSMENT_FREEZE.is_file() or ASSESSMENT_FREEZE.read_bytes() != frozen:
        raise FinalizationError("Extension assessment freeze is missing or differs")
    extension = extension_summary()
    combined = combined_summary(extension)
    package_engine.write_bytes(SUMMARY_YAML, package_engine.yaml_bytes(extension))
    package_engine.write_bytes(SUMMARY_MD, extension_markdown(extension))
    package_engine.write_bytes(COMBINED_YAML, package_engine.yaml_bytes(combined))
    package_engine.write_bytes(COMBINED_MD, combined_markdown(combined))
    report = {
        "schema_version": 1,
        "task_id": "08-hegota-prospective-complexity-assessment-sfi-cfi-validation",
        "extension_id": "sfi-cfi-2026-08-26",
        "snapshot_id": "hegota-sfi-cfi-2026-08-26-ac450a4",
        "result": "pass",
        "publication_label": "Hegotá SFI'd/CFI'd EIPs at the time of the 2026-08-26 snapshot",
        "cohort": {
            "entries": 2,
            "scheduled_for_inclusion": [7805],
            "considered_for_inclusion": [8141],
            "owner_review_approved": True,
        },
        "method": {
            "eips_commit": "ac450a4ab2f37387385ee9c54b62f518d97e6cc9",
            "information_cutoff_at": "2026-08-25T11:56:58Z",
            "rubric_commit": "3d8c0128c5543dd3146341ef395aa344e4abea30",
            "checklist_revision": 2,
            "model": "gpt-5.6-sol",
            "reasoning_effort": "xhigh",
            "isolation": "bubblewrap_one_eip_capsule_v1",
            "isolation_self_test_passed": True,
            "maximum_concurrency": 2,
        },
        "original_task_08": {
            "packages": 37,
            "assessments": 37,
            "package_freeze_sha256": ORIGINAL_HASHES[ORIGINAL_PACKAGE_FREEZE],
            "assessment_freeze_sha256": ORIGINAL_HASHES[ORIGINAL_ASSESSMENT_FREEZE],
            "artifacts_changed": 0,
        },
        "extension_packages": {
            "validated": 2,
            "package_freeze_sha256": package_engine.file_sha256(PACKAGE_FREEZE),
            "byte_identical_regeneration": True,
            "unavailable_snapshot_link": {
                "eip": 7562,
                "referenced_by": 8141,
                "handling": "recorded_absent_at_snapshot_without_later_substitution",
            },
        },
        "extension_assessments": {
            "validated": 2,
            "assessment_freeze_sha256": package_engine.file_sha256(ASSESSMENT_FREEZE),
            "raw_outputs": load(ASSESSMENT_FREEZE)["raw_output_count"],
            "contaminated": 0,
        },
        "summaries": {
            "extension_yaml_sha256": package_engine.file_sha256(SUMMARY_YAML),
            "extension_markdown_sha256": package_engine.file_sha256(SUMMARY_MD),
            "combined_yaml_sha256": package_engine.file_sha256(COMBINED_YAML),
            "combined_markdown_sha256": package_engine.file_sha256(COMBINED_MD),
            "original_pfi_score_sum": 776,
            "extension_score_sum": extension["el_rubric_total"]["score_sum"],
            "combined_score_sum": combined["el_rubric_totals"]["all_candidates"]["score_sum"],
            "combined_scored_denominator": 39,
        },
    }
    package_engine.write_bytes(VALIDATION_REPORT, package_engine.yaml_bytes(report))
    print(f"rendered extension summary: {SUMMARY_MD}")
    print(f"rendered combined summary: {COMBINED_MD}")
    print(f"wrote extension validation report: {VALIDATION_REPORT}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--summarize", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        freeze()
    else:
        summarize()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FinalizationError, KeyError, TypeError) as error:
        raise SystemExit(f"extension finalization error: {error}") from error
