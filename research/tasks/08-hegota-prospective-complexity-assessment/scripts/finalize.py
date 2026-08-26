#!/usr/bin/env python3
"""Freeze Task 08 assessments, then render deterministic summaries."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from engine_adapter import REPO_ROOT, TASK_ROOT, package_engine
from validate_assessment import NAMESPACE, OUTPUT_ROOT, validate
from validate_packages import REVIEW_PATH


ASSESSMENT_FREEZE = TASK_ROOT / "outputs" / "assessment-manifest.yaml"
SUMMARY_YAML = TASK_ROOT / "outputs" / "summary.yaml"
SUMMARY_MD = TASK_ROOT / "outputs" / "summary.md"
RAW_ROOT = TASK_ROOT / "outputs" / "raw" / NAMESPACE
COHORT_PATH = TASK_ROOT / "inputs" / "hegota-pfi-2026-08-26.yaml"

load_yaml = package_engine.load_yaml
file_sha256 = package_engine.file_sha256
write_bytes = package_engine.write_bytes
yaml_bytes = package_engine.yaml_bytes


class FinalizationError(RuntimeError):
    """Raised when freeze order or deterministic aggregation is violated."""


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def review_entries() -> list[dict[str, Any]]:
    review = load_yaml(REVIEW_PATH)
    if review.get("review_gate", {}).get("status") != "approved":
        raise FinalizationError("Cohort review is not approved")
    return review["entries"]


def assessment_inventory() -> dict[str, Any]:
    entries = review_entries()
    scorable = [item for item in entries if item["disposition"] == "score_el_rubric"]
    records: list[dict[str, Any]] = []
    for entry in scorable:
        number = int(entry["eip"])
        output = OUTPUT_ROOT / f"eip-{number}.yaml"
        validate("hegota", number)
        raw = RAW_ROOT / f"eip-{number}.yaml"
        records.append(
            {
                "eip": number,
                "assessment_path": rel(output),
                "assessment_sha256": file_sha256(output),
                "raw_output": (
                    {"path": rel(raw), "content_sha256": file_sha256(raw)}
                    if raw.is_file()
                    else None
                ),
            }
        )
    actual = sorted(
        int(path.stem.removeprefix("eip-")) for path in OUTPUT_ROOT.glob("eip-*.yaml")
    )
    expected = sorted(int(item["eip"]) for item in scorable)
    if actual != expected:
        raise FinalizationError(
            f"Canonical assessment inventory mismatch: expected={expected}, actual={actual}"
        )
    return {
        "schema_version": 1,
        "task_id": "08-hegota-prospective-complexity-assessment-result-freeze",
        "snapshot_id": "hegota-pfi-2026-08-26-ac450a4",
        "cohort_review": {"path": rel(REVIEW_PATH), "content_sha256": file_sha256(REVIEW_PATH)},
        "assessment_count": len(records),
        "raw_output_count": sum(item["raw_output"] is not None for item in records),
        "assessments": records,
    }


def summary_data() -> dict[str, Any]:
    frozen = yaml_bytes(assessment_inventory())
    if not ASSESSMENT_FREEZE.is_file() or ASSESSMENT_FREEZE.read_bytes() != frozen:
        raise FinalizationError("Assessment hash freeze is missing or differs from canonical results")
    cohort = load_yaml(COHORT_PATH)
    entries = review_entries()
    scored_rows: list[dict[str, Any]] = []
    not_applicable: list[dict[str, Any]] = []
    for entry in entries:
        number = int(entry["eip"])
        if entry["disposition"] == "score_el_rubric":
            assessment = load_yaml(OUTPUT_ROOT / f"eip-{number}.yaml")
            scored_rows.append(
                {
                    "eip": number,
                    "title": entry["canonical_title"],
                    "affected_layers": entry["affected_layers"],
                    "score": assessment["totals"]["primary_score"],
                    "tier": assessment["totals"]["complexity_tier"],
                    "confidence": assessment["overall_confidence"],
                    "under_specification": assessment["under_specification"]["present"],
                }
            )
        else:
            kind = (
                "consensus_only"
                if entry["affected_layers"] == ["consensus"]
                else "explicit_owner_exclusion"
            )
            not_applicable.append(
                {
                    "eip": number,
                    "title": entry["canonical_title"],
                    "affected_layers": entry["affected_layers"],
                    "exclusion_kind": kind,
                    "rationale": entry["rationale"],
                }
            )
    tiers = Counter(item["tier"] for item in scored_rows)
    confidence = Counter(item["confidence"] for item in scored_rows)
    total = sum(item["score"] for item in scored_rows)
    return {
        "schema_version": 1,
        "task_id": "08-hegota-prospective-complexity-assessment-summary",
        "snapshot": {
            "snapshot_id": cohort["snapshot_id"],
            "captured_on": cohort["captured_on"],
            "repository": cohort["source"]["repository"],
            "commit": cohort["source"]["repository_commit"],
            "information_cutoff_at": cohort["source"]["committed_at"],
        },
        "population": {
            "pfi_entries": 44,
            "scored_el_rubric": len(scored_rows),
            "not_applicable_total": len(not_applicable),
            "consensus_only_not_applicable": sum(
                item["exclusion_kind"] == "consensus_only" for item in not_applicable
            ),
            "explicit_owner_exclusions": sum(
                item["exclusion_kind"] == "explicit_owner_exclusion"
                for item in not_applicable
            ),
            "completed_assessments": len(scored_rows),
            "validated_assessments": len(scored_rows),
        },
        "el_rubric_total": {
            "score_sum": total,
            "scored_denominator": len(scored_rows),
            "label": f"EL-rubric total: {total} across {len(scored_rows)} scored PFI EIPs",
        },
        "distributions": {
            "tiers": {name: tiers.get(name, 0) for name in ("low", "medium", "high")},
            "confidence": {
                name: confidence.get(name, 0) for name in ("low", "medium", "high")
            },
            "under_specification": {
                "present": sum(item["under_specification"] for item in scored_rows),
                "absent": sum(not item["under_specification"] for item in scored_rows),
            },
        },
        "scored_eips": scored_rows,
        "not_applicable_eips": not_applicable,
        "caveats": [
            "Scores cover execution-layer and execution-client-networking surfaces only; cross-layer consensus work is not scored.",
            "EIP-8163 and EIP-8173 were explicitly excluded by the project owner because they introduce no current L1 protocol or client behavior change.",
            "Proposal splitting and cross-EIP interactions can overlap complexity, so the score sum is not an additive estimate of implementation effort.",
            "The PFI snapshot may change after the frozen information cutoff; later scope churn is outside this study.",
            "No consensus-layer rubric was applied, so this is not a total-complexity estimate for all Hegota protocol work.",
        ],
    }


def markdown(summary: dict[str, Any]) -> bytes:
    population = summary["population"]
    lines = [
        "# Hegotá PFI prospective execution-layer complexity",
        "",
        f"Snapshot: `{summary['snapshot']['snapshot_id']}` at `{summary['snapshot']['commit']}` "
        f"(information cutoff `{summary['snapshot']['information_cutoff_at']}`).",
        "",
        f"**{summary['el_rubric_total']['label']}**. "
        f"Of 44 PFI entries, {population['consensus_only_not_applicable']} are consensus-only "
        f"and {population['explicit_owner_exclusions']} were explicitly excluded; none received a numeric score or tier.",
        "",
        "## Scored execution-layer surfaces",
        "",
        "| EIP | Proposal | Layers | Score | Tier | Confidence | Under-specified |",
        "|---:|---|---|---:|---|---|---|",
    ]
    for item in summary["scored_eips"]:
        title = item["title"].replace("|", "\\|")
        layers = ", ".join(item["affected_layers"])
        lines.append(
            f"| EIP-{item['eip']} | {title} | {layers} | {item['score']} | "
            f"{item['tier']} | {item['confidence']} | "
            f"{'yes' if item['under_specification'] else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Not applicable to this rubric",
            "",
            "| EIP | Proposal | Basis | Rationale |",
            "|---:|---|---|---|",
        ]
    )
    for item in summary["not_applicable_eips"]:
        title = item["title"].replace("|", "\\|")
        rationale = item["rationale"].replace("|", "\\|")
        basis = item["exclusion_kind"].replace("_", " ")
        lines.append(f"| EIP-{item['eip']} | {title} | {basis} | {rationale} |")
    lines.extend(["", "## Caveats", ""])
    lines.extend(f"- {item}" for item in summary["caveats"])
    lines.append("")
    return "\n".join(lines).encode()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--summarize", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.freeze:
        write_bytes(ASSESSMENT_FREEZE, yaml_bytes(assessment_inventory()))
        print(f"froze assessment hashes: {ASSESSMENT_FREEZE}")
    else:
        summary = summary_data()
        write_bytes(SUMMARY_YAML, yaml_bytes(summary))
        write_bytes(SUMMARY_MD, markdown(summary))
        print(f"rendered summary: {SUMMARY_YAML}")
        print(f"rendered summary: {SUMMARY_MD}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FinalizationError, KeyError, TypeError) as error:
        raise SystemExit(f"finalization error: {error}") from error
