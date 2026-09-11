#!/usr/bin/env python3
"""Validate the append-only Hegotá SFI/CFI extension snapshot."""

from __future__ import annotations

import argparse
from pathlib import Path

import validate_cohort as engine
from engine_adapter import REPO_ROOT, TASK_ROOT, package_engine


EXTENSION_ROOT = TASK_ROOT / "extensions" / "sfi-cfi-2026-08-26"
MANIFEST_PATH = EXTENSION_ROOT / "inputs" / "cohort.yaml"
REVIEW_PATH = EXTENSION_ROOT / "outputs" / "cohort-review.yaml"
EXPECTED_SNAPSHOT = "hegota-sfi-cfi-2026-08-26-ac450a4"
EXPECTED_STATUS = {7805: "SFI", 8141: "CFI"}


def validate(eips_repo: Path) -> tuple[str, int]:
    manifest = engine.load_yaml(MANIFEST_PATH)
    engine.require_equal("schema_version", manifest.get("schema_version"), 1)
    engine.require_equal(
        "task_id",
        manifest.get("task_id"),
        "08-hegota-prospective-complexity-assessment",
    )
    engine.require_equal("snapshot_id", manifest.get("snapshot_id"), EXPECTED_SNAPSHOT)
    engine.require_equal(
        "parent_snapshot_id",
        manifest.get("parent_snapshot_id"),
        "hegota-pfi-2026-08-26-ac450a4",
    )

    source = manifest["source"]
    commit = source["repository_commit"]
    path = source["path"]
    engine.git(eips_repo, "rev-parse", "--verify", f"{commit}^{{commit}}")
    parent = engine.git(eips_repo, "rev-parse", f"{commit}^").decode().strip()
    engine.require_equal("source.parent_commit", parent, source["parent_commit"])
    committed_at = engine.git(
        eips_repo, "show", "-s", "--format=%cI", commit
    ).decode().strip()
    engine.require_equal(
        "source.committed_at",
        engine.normalize_timestamp(committed_at),
        source["committed_at"],
    )
    subject = engine.git(eips_repo, "show", "-s", "--format=%s", commit).decode().strip()
    engine.require_equal("source.commit_subject", subject, source["commit_subject"])

    meta_bytes = engine.git(eips_repo, "show", f"{commit}:{path}")
    meta_blob = engine.git(eips_repo, "rev-parse", f"{commit}:{path}").decode().strip()
    engine.require_equal("source.git_blob_sha", meta_blob, source["git_blob_sha"])
    engine.require_equal("source.content_sha256", engine.sha256(meta_bytes), source["content_sha256"])
    meta = engine.frontmatter(meta_bytes, path)
    engine.require_equal("EIP-8081 frontmatter eip", meta.get("eip"), 8081)
    engine.require_equal("EIP-8081 frontmatter title", meta.get("title"), "Hardfork Meta - Hegotá")

    text = meta_bytes.decode("utf-8")
    scheduled = engine.section_items(text, "EIPs Scheduled for Inclusion")
    considered = engine.section_items(text, "Considered for Inclusion")
    inventory = manifest["inventory"]
    engine.require_equal("extension inventory size", len(inventory), 2)
    engine.require_equal(
        "scheduled selection",
        [number for number, _ in scheduled],
        manifest["selection"]["sections"]["scheduled_for_inclusion"],
    )
    engine.require_equal(
        "considered selection",
        [number for number, _ in considered],
        manifest["selection"]["sections"]["considered_for_inclusion"],
    )
    listed = dict(scheduled + considered)
    engine.require_equal("extension EIP order", [item["eip"] for item in inventory], [7805, 8141])

    for item in inventory:
        number = int(item["eip"])
        expected_path = f"EIPS/eip-{number}.md"
        engine.require_equal(f"EIP-{number} path", item["path"], expected_path)
        engine.require_equal(f"EIP-{number} listed title", item["listed_title"], listed[number])
        engine.require_equal(f"EIP-{number} snapshot status", item["snapshot_status"], EXPECTED_STATUS[number])
        eip_bytes = engine.git(eips_repo, "show", f"{commit}:{expected_path}")
        eip_blob = engine.git(eips_repo, "rev-parse", f"{commit}:{expected_path}").decode().strip()
        fields = engine.frontmatter(eip_bytes, expected_path)
        engine.require_equal(f"EIP-{number} blob", item["git_blob_sha"], eip_blob)
        engine.require_equal(f"EIP-{number} content", item["content_sha256"], engine.sha256(eip_bytes))
        engine.require_equal(f"EIP-{number} frontmatter eip", fields.get("eip"), number)
        engine.require_equal(f"EIP-{number} title", fields.get("title"), item["canonical_title"])
        engine.require_equal(f"EIP-{number} type", fields.get("type"), item["eip_type"])
        engine.require_equal(f"EIP-{number} category", fields.get("category"), item["category"])

    review = engine.load_yaml(REVIEW_PATH)
    expected_review_hash = package_engine.file_sha256(MANIFEST_PATH)
    engine.require_equal(
        "review cohort hash",
        review["cohort_manifest"]["content_sha256"],
        expected_review_hash,
    )
    engine.require_equal("review gate", review["review_gate"]["status"], "approved")
    engine.require_equal("review order", [item["eip"] for item in review["entries"]], [7805, 8141])
    for item in review["entries"]:
        number = int(item["eip"])
        engine.require_equal(f"EIP-{number} review status", item["review"]["status"], "approved")
        engine.require_equal(f"EIP-{number} disposition", item["disposition"], "score_el_rubric")
        engine.require_equal(f"EIP-{number} review snapshot status", item["snapshot_status"], EXPECTED_STATUS[number])
    return manifest["snapshot_id"], len(inventory)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eips-repo", type=Path, default=REPO_ROOT.parent / "EIPs")
    args = parser.parse_args()
    snapshot, count = validate(args.eips_repo.resolve())
    print(f"Validated {count} Hegotá SFI/CFI entries for {snapshot}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (engine.CohortError, KeyError, TypeError) as error:
        raise SystemExit(f"extension cohort validation error: {error}") from error
