#!/usr/bin/env python3
"""Build and freeze the two deterministic SFI/CFI extension packages."""

from __future__ import annotations

import argparse
import copy
import tempfile
from pathlib import Path
from typing import Any

import prepare_packages as builder
from engine_adapter import REPO_ROOT, TASK_ROOT, package_engine
from validate_sfi_cfi_cohort import validate as validate_cohort


EXTENSION_ROOT = TASK_ROOT / "extensions" / "sfi-cfi-2026-08-26"
COHORT_PATH = EXTENSION_ROOT / "inputs" / "cohort.yaml"
REVIEW_PATH = EXTENSION_ROOT / "outputs" / "cohort-review.yaml"
PACKAGE_ROOT = EXTENSION_ROOT / "inputs" / "packages"
PROMPT_ROOT = EXTENSION_ROOT / "inputs" / "prompts"
PACKAGE_FREEZE = EXTENSION_ROOT / "outputs" / "package-manifest.yaml"
TASK_CONTRACT = EXTENSION_ROOT / "TASK.md"
ASSESSOR_PROMPT = EXTENSION_ROOT / "prompts" / "assessor.md"
ADAPTER_PATH = Path(__file__).resolve()
SHARED_SUPPORTING_DOCUMENTS = builder.supporting_documents
UNAVAILABLE_EIP_7562 = {
    "repository": "ethereum/EIPs",
    "commit": "ac450a4ab2f37387385ee9c54b62f518d97e6cc9",
    "path": "EIPS/eip-7562.md",
    "immutable_url": "https://github.com/ethereum/EIPs/blob/ac450a4ab2f37387385ee9c54b62f518d97e6cc9/EIPS/eip-7562.md",
    "availability": "absent_at_snapshot",
    "reason": "EIP-8141 cites ERC-7562, but EIPS/eip-7562.md does not exist at the frozen EIPs commit; no later replacement or text was substituted.",
}


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def approved_entries() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    cohort = package_engine.load_yaml(COHORT_PATH)
    review = package_engine.load_yaml(REVIEW_PATH)
    inventory = cohort.get("inventory", [])
    entries = review.get("entries", [])
    if review.get("review_gate", {}).get("status") != "approved":
        raise package_engine.InputError("The SFI/CFI extension review is not approved")
    if [item.get("eip") for item in entries] != [item.get("eip") for item in inventory]:
        raise package_engine.InputError("Extension review order differs from its source manifest")
    if [item.get("eip") for item in entries] != [7805, 8141]:
        raise package_engine.InputError("Expected exactly EIP-7805 and EIP-8141")
    if not all(
        item.get("disposition") == "score_el_rubric"
        and item.get("review", {}).get("status") == "approved"
        for item in entries
    ):
        raise package_engine.InputError("Both extension entries must be approved for EL scoring")
    return cohort, review, entries


def render_prompt(number: int, title: str) -> bytes:
    text = ASSESSOR_PROMPT.read_text(encoding="utf-8")
    text = text.replace(
        "# Perform one isolated Hegotá snapshot complexity assessment",
        f"# Perform one isolated Hegotá snapshot complexity assessment: EIP-{number}",
        1,
    )
    text = text.replace(
        "You are assessing exactly one Ethereum proposal as it appears in the Hegotá 2026-08-26 snapshot sealed in `package/`.",
        f"You are assessing exactly EIP-{number}, {title}, as it appears in the Hegotá 2026-08-26 snapshot sealed in `package/`.",
        1,
    )
    return text.encode()


def supporting_documents(**kwargs):
    """Reuse Task 05 discovery while preserving EIP-8141's frozen broken link."""
    eip_text = kwargs["eip_text"]
    if "./eip-7562.md" in eip_text:
        kwargs = {
            **kwargs,
            "eip_text": eip_text.replace("./eip-7562.md", "./unavailable-7562.md"),
        }
    return SHARED_SUPPORTING_DOCUMENTS(**kwargs)


def configure() -> None:
    builder.COHORT_PATH = COHORT_PATH
    builder.REVIEW_PATH = REVIEW_PATH
    builder.PACKAGE_NAMESPACE = "hegota-sfi-cfi-2026-08-26"
    builder.PACKAGE_ROOT = PACKAGE_ROOT
    builder.PROMPT_ROOT = PROMPT_ROOT
    builder.TASK_CONTRACT = TASK_CONTRACT
    builder.ASSESSOR_PROMPT = ASSESSOR_PROMPT
    builder.PACKAGE_FREEZE = PACKAGE_FREEZE
    builder.approved_entries = approved_entries
    builder.render_prompt = render_prompt
    builder.supporting_documents = supporting_documents


def annotate_packages(root: Path) -> None:
    _, review, entries = approved_entries()
    by_number = {int(item["eip"]): item for item in entries}
    for package in sorted(path for path in root.glob("eip-*") if path.is_dir()):
        number = int(package.name.removeprefix("eip-"))
        manifest_path = package / "manifest.yaml"
        manifest = package_engine.load_yaml(manifest_path)
        manifest["snapshot_selection_status"] = by_number[number]["snapshot_status"]
        manifest["preparation"]["extension_adapter"] = {
            "path": rel(ADAPTER_PATH),
            "content_sha256": package_engine.file_sha256(ADAPTER_PATH),
        }
        manifest["unavailable_same_snapshot_links"] = (
            [copy.deepcopy(UNAVAILABLE_EIP_7562)] if number == 8141 else []
        )
        package_engine.write_bytes(manifest_path, package_engine.yaml_bytes(manifest))
        template_path = package / "output-template.yaml"
        template = package_engine.load_yaml(template_path)
        template["provenance"]["input_package"]["manifest_sha256"] = (
            package_engine.file_sha256(manifest_path)
        )
        package_engine.write_bytes(template_path, package_engine.yaml_bytes(template))


def build(target_packages: Path, target_prompts: Path, eips_repo: Path, pm_repo: Path) -> None:
    configure()
    builder.build_packages(
        target_package_root=target_packages,
        target_prompt_root=target_prompts,
        eips_repo=eips_repo,
        pm_repo=pm_repo,
        external_repos={},
        write_common_rubric=False,
    )
    annotate_packages(target_packages)


def inventory() -> dict[str, Any]:
    configure()
    data = builder.package_inventory()
    data["extension_id"] = "sfi-cfi-2026-08-26"
    data["publication_label"] = "Hegotá SFI'd/CFI'd EIPs at the time of the 2026-08-26 snapshot"
    data["parent_package_freeze"] = {
        "path": "research/tasks/08-hegota-prospective-complexity-assessment/outputs/package-manifest.yaml",
        "content_sha256": "5e7c447d725a7cc8779bd363b0075450ac629dc01306a5328136d8d7084c0468",
    }
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eips-repo", type=Path, default=REPO_ROOT.parent / "EIPs")
    parser.add_argument("--pm-repo", type=Path, default=REPO_ROOT.parent / "pm")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--verify-regeneration", action="store_true")
    args = parser.parse_args()
    eips_repo = args.eips_repo.resolve()
    pm_repo = args.pm_repo.resolve()
    validate_cohort(eips_repo)
    if args.prepare:
        build(PACKAGE_ROOT, PROMPT_ROOT, eips_repo, pm_repo)
    elif args.freeze:
        package_engine.write_bytes(PACKAGE_FREEZE, package_engine.yaml_bytes(inventory()))
        print(f"froze extension package inventory: {PACKAGE_FREEZE}")
    else:
        with tempfile.TemporaryDirectory(prefix="hegota-sfi-cfi-regeneration-") as raw:
            temporary = Path(raw)
            build(temporary / "packages", temporary / "prompts", eips_repo, pm_repo)
            builder.compare_tree(PACKAGE_ROOT, temporary / "packages")
            builder.compare_tree(PROMPT_ROOT, temporary / "prompts")
        expected = package_engine.yaml_bytes(inventory())
        if not PACKAGE_FREEZE.is_file() or PACKAGE_FREEZE.read_bytes() != expected:
            raise package_engine.InputError("Extension package freeze is missing or differs")
        print("verified byte-identical regeneration of both SFI/CFI packages and prompts")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (package_engine.InputError, KeyError, TypeError) as error:
        raise SystemExit(f"extension input error: {error}") from error
