#!/usr/bin/env python3
"""Build and freeze deterministic Hegota prospective assessment packages."""

from __future__ import annotations

import argparse
import copy
import tempfile
from pathlib import Path
from typing import Any

from engine_adapter import REPO_ROOT, TASK05_ROOT, TASK_ROOT, package_engine


CONFIG_PATH = TASK_ROOT / "config.yaml"
COHORT_PATH = TASK_ROOT / "inputs" / "hegota-pfi-2026-08-26.yaml"
REVIEW_PATH = TASK_ROOT / "outputs" / "cohort-review.yaml"
PACKAGE_NAMESPACE = "hegota-pfi-2026-08-26"
PACKAGE_ROOT = TASK_ROOT / "inputs" / "packages" / PACKAGE_NAMESPACE
PROMPT_ROOT = TASK_ROOT / "inputs" / "prompts" / PACKAGE_NAMESPACE
RUBRIC_ROOT = TASK_ROOT / "inputs" / "rubric"
TASK_CONTRACT = TASK_ROOT / "TASK.md"
ASSESSOR_PROMPT = TASK_ROOT / "prompts" / "assessor.md"
ASSESSMENT_CONTRACT = TASK_ROOT / "prompts" / "ASSESSMENT-CONTRACT.md"
TASK05_TEMPLATE = TASK05_ROOT / "templates" / "output.yaml"
PACKAGE_FREEZE = TASK_ROOT / "outputs" / "package-manifest.yaml"

load_yaml = package_engine.load_yaml
yaml_bytes = package_engine.yaml_bytes
sha256 = package_engine.sha256
file_sha256 = package_engine.file_sha256
write_bytes = package_engine.write_bytes
git_blob = package_engine.git_blob
git_commit_time = package_engine.git_commit_time
supporting_documents = package_engine.supporting_documents
transform_rubric = package_engine.transform_rubric
external_repo_map = package_engine.external_repo_map
InputError = package_engine.InputError
PROVENANCE_ONLY_REPOSITORIES = {
    *package_engine.PROVENANCE_ONLY_REPOSITORIES,
    "ethereum/consensus-specs",
}


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def approved_entries() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    cohort = load_yaml(COHORT_PATH)
    review = load_yaml(REVIEW_PATH)
    if review.get("review_gate", {}).get("status") != "approved":
        raise InputError("The cohort review gate is not approved")
    inventory = cohort.get("inventory", [])
    entries = review.get("entries", [])
    if [item.get("eip") for item in entries] != [item.get("eip") for item in inventory]:
        raise InputError("Cohort-review order differs from the frozen source manifest")
    if len(entries) != 44 or not all(
        item.get("review", {}).get("status") == "approved" for item in entries
    ):
        raise InputError("All 44 cohort-review entries must be approved")
    scorable = [
        item for item in entries if item.get("disposition") == "score_el_rubric"
    ]
    if len(scorable) != 37:
        raise InputError(f"Expected 37 scorable entries, found {len(scorable)}")
    return cohort, review, scorable


def rubric_material(pm_repo: Path, config: dict[str, Any]) -> tuple[bytes, bytes, dict[str, Any]]:
    expected = config["rubric"]
    source, blob = git_blob(pm_repo, expected["repository_commit"], expected["path"])
    if blob != expected["git_blob_sha"]:
        raise InputError(f"Rubric Git blob mismatch: {blob}")
    if sha256(source) != expected["content_sha256"]:
        raise InputError("Rubric content SHA-256 mismatch")
    view = transform_rubric(source)
    task05_view = TASK05_ROOT / "inputs" / "rubric" / "assessor-view.md"
    if view != task05_view.read_bytes():
        raise InputError("Task 08 assessor view differs from the frozen Task 05 assessor view")
    manifest = {
        "schema_version": 1,
        "source": copy.deepcopy(expected),
        "source_file": {"path": rel(RUBRIC_ROOT / "source.md"), "content_sha256": sha256(source)},
        "assessor_view": {
            "path": rel(RUBRIC_ROOT / "assessor-view.md"),
            "content_sha256": sha256(view),
            "transformation": "remove_revision_notes_and_calibration_examples_v1",
            "normative_criteria_preserved": True,
            "tier_definitions_preserved": True,
            "task_05_assessor_view": {
                "path": rel(task05_view),
                "content_sha256": file_sha256(task05_view),
            },
        },
    }
    return source, view, manifest


def render_prompt(number: int, title: str) -> bytes:
    text = ASSESSOR_PROMPT.read_text(encoding="utf-8")
    text = text.replace(
        "# Perform one isolated Hegotá snapshot complexity assessment",
        f"# Perform one isolated Hegotá snapshot complexity assessment: EIP-{number}",
        1,
    )
    text = text.replace(
        "You are assessing exactly one Ethereum proposal as it appears in the Hegotá PFI snapshot sealed in `package/`.",
        f"You are assessing exactly EIP-{number}, {title}, as it appears in the Hegotá PFI snapshot sealed in `package/`.",
        1,
    )
    return text.encode()


def output_template(
    *,
    entry: dict[str, Any],
    package_manifest_path: Path,
    package_manifest_sha: str,
    cohort: dict[str, Any],
    rubric: dict[str, Any],
    prompt_path: Path,
    prompt_sha: str,
    assessment_sources: list[str],
    primary: dict[str, Any],
) -> dict[str, Any]:
    result = load_yaml(TASK05_TEMPLATE)
    number = int(entry["eip"])
    result["task_id"] = "08-hegota-prospective-complexity-assessment"
    result["fork_id"] = "hegota"
    result["snapshot_id"] = cohort["snapshot_id"]
    result["eip"] = {
        "number": number,
        "title": entry["canonical_title"],
        "layers": copy.deepcopy(entry["affected_layers"]),
    }
    result["assessment"] = {"snapshot_scope_summary": None}
    original_provenance = result["provenance"]
    source = rubric["source"]
    result["provenance"] = {
        "input_package": {
            "manifest_path": rel(package_manifest_path),
            "manifest_sha256": package_manifest_sha,
        },
        "cohort_snapshot": {
            "snapshot_id": cohort["snapshot_id"],
            "manifest_path": rel(COHORT_PATH),
            "manifest_sha256": file_sha256(COHORT_PATH),
            "captured_on": cohort["captured_on"],
            "repository": cohort["source"]["repository"],
            "commit": cohort["source"]["repository_commit"],
            "committed_at": cohort["source"]["committed_at"],
            "information_cutoff_at": cohort["source"]["committed_at"],
        },
        "snapshot_eip": copy.deepcopy(primary),
        "rubric_source": {
            "repository": source["repository"],
            "commit": source["repository_commit"],
            "path": source["path"],
            "git_blob_sha": source["git_blob_sha"],
            "content_sha256": source["content_sha256"],
            "immutable_url": source["immutable_url"],
            "checklist_revision": source["checklist_revision"],
        },
        "assessor_view": {
            "path": "rubric.md",
            "content_sha256": rubric["assessor_view"]["content_sha256"],
            "transformation": rubric["assessor_view"]["transformation"],
        },
        "task_contract": {
            "path": rel(TASK_CONTRACT),
            "content_sha256": file_sha256(TASK_CONTRACT),
        },
        "assessment_contract": {
            "path": rel(ASSESSMENT_CONTRACT),
            "content_sha256": file_sha256(ASSESSMENT_CONTRACT),
        },
        "session_prompt": {"path": rel(prompt_path), "content_sha256": prompt_sha},
        "assessor": copy.deepcopy(original_provenance["assessor"]),
        "sources_consulted": copy.deepcopy(assessment_sources),
        "operational_files_read": [
            "PROMPT.md",
            "ASSESSMENT-CONTRACT.md",
            "package/manifest.yaml",
            "package/output-template.yaml",
        ],
    }
    for criterion in result["criteria"]:
        criterion["evidence"] = [{"source": None, "locator": None, "summary": None}]
    control = result.pop("hindsight_control")
    result["information_control"] = {
        "internet_access_attempted": control["internet_access_attempted"],
        "post_snapshot_information_exposure": False,
        "prohibited_source_exposure": control["prohibited_source_exposure"],
        "exposure_details": control["exposure_details"],
        "contaminated": control["contaminated"],
        "attestation": control["attestation"],
    }
    return result


def build_packages(
    *,
    target_package_root: Path,
    target_prompt_root: Path,
    eips_repo: Path,
    pm_repo: Path,
    external_repos: dict[str, Path],
    write_common_rubric: bool,
) -> list[int]:
    config = load_yaml(CONFIG_PATH)
    cohort, _, entries = approved_entries()
    source, rubric_view, rubric = rubric_material(pm_repo, config)
    if write_common_rubric:
        write_bytes(RUBRIC_ROOT / "source.md", source)
        write_bytes(RUBRIC_ROOT / "assessor-view.md", rubric_view)
        write_bytes(RUBRIC_ROOT / "manifest.yaml", yaml_bytes(rubric))

    source_commit = cohort["source"]["repository_commit"]
    commit_time = git_commit_time(eips_repo, source_commit)
    if commit_time != cohort["source"]["committed_at"]:
        raise InputError("Pinned EIPs commit time differs from the cohort manifest")
    inventory = {int(item["eip"]): item for item in cohort["inventory"]}
    prepared: list[int] = []
    for entry in entries:
        number = int(entry["eip"])
        source_record = inventory[number]
        package_dir = target_package_root / f"eip-{number}"
        eip_data, eip_blob = git_blob(eips_repo, source_commit, source_record["path"])
        metadata = package_engine.frontmatter(eip_data.decode())
        if metadata.get("eip") != number or metadata.get("title") != entry["canonical_title"]:
            raise InputError(f"EIP-{number} frontmatter differs from the approved cohort review")
        write_bytes(package_dir / "eip.md", eip_data)
        write_bytes(package_dir / "rubric.md", rubric_view)
        supporting, provenance_only = supporting_documents(
            eips_repo=eips_repo,
            selected_commit=source_commit,
            information_cutoff_at=cohort["source"]["committed_at"],
            eip_text=eip_data.decode(),
            package_dir=package_dir,
            external_repos=external_repos,
            provenance_only_repositories=PROVENANCE_ONLY_REPOSITORIES,
            provenance_only_reason=(
                "Task 08 excludes implementation and test repositories and, for cross-layer "
                "proposals, consensus-spec documents from execution-layer scoring evidence."
            ),
        )
        prompt_path = target_prompt_root / f"eip-{number}.md"
        prompt = render_prompt(number, entry["canonical_title"])
        write_bytes(prompt_path, prompt)
        primary = {
            "package_path": "eip.md",
            "repository": cohort["source"]["repository"],
            "commit": source_commit,
            "path": source_record["path"],
            "committed_at": commit_time,
            "git_blob_sha": eip_blob,
            "content_sha256": sha256(eip_data),
            "immutable_url": (
                f"https://github.com/ethereum/EIPs/blob/{source_commit}/{source_record['path']}"
            ),
            "information_cutoff_at": cohort["source"]["committed_at"],
        }
        assessment_sources = [
            "eip.md",
            "rubric.md",
            *[item["package_path"] for item in supporting],
        ]
        canonical_package = PACKAGE_ROOT / f"eip-{number}"
        canonical_prompt = PROMPT_ROOT / f"eip-{number}.md"
        manifest = {
            "schema_version": 1,
            "task_id": "08-hegota-prospective-complexity-assessment",
            "fork_id": "hegota",
            "snapshot_id": cohort["snapshot_id"],
            "eip": {
                "number": number,
                "title": entry["canonical_title"],
                "layers": copy.deepcopy(entry["affected_layers"]),
            },
            "cohort_manifest": {
                "path": rel(COHORT_PATH),
                "content_sha256": file_sha256(COHORT_PATH),
                "snapshot_id": cohort["snapshot_id"],
            },
            "cohort_review": {
                "path": rel(REVIEW_PATH),
                "content_sha256": file_sha256(REVIEW_PATH),
                "review_status": entry["review"]["status"],
                "review_date": entry["review"]["review_date"],
                "disposition": entry["disposition"],
                "affected_layers": copy.deepcopy(entry["affected_layers"]),
            },
            "snapshot_eip": primary,
            "rubric": {
                **copy.deepcopy(rubric["source"]),
                "package_path": "rubric.md",
                "assessor_view_sha256": rubric["assessor_view"]["content_sha256"],
                "transformation": rubric["assessor_view"]["transformation"],
            },
            "supporting_documents": supporting,
            "provenance_only_links": provenance_only,
            "assessment_source_files": assessment_sources,
            "source_policy": {
                "internet_allowed": False,
                "follow_links_allowed": False,
                "files_outside_package_allowed": False,
                "dedicated_assessment_skill_allowed": False,
                "opportunistic_repository_evidence_allowed": False,
                "post_snapshot_information_allowed": False,
                "provenance_only_repositories": sorted(
                    PROVENANCE_ONLY_REPOSITORIES
                ),
            },
            "operational_files": {
                "task_contract": {"path": rel(TASK_CONTRACT), "content_sha256": file_sha256(TASK_CONTRACT)},
                "assessment_contract": {"path": rel(ASSESSMENT_CONTRACT), "content_sha256": file_sha256(ASSESSMENT_CONTRACT)},
                "session_prompt": {"path": rel(canonical_prompt), "content_sha256": sha256(prompt)},
                "output_template_source": {"path": rel(TASK05_TEMPLATE), "content_sha256": file_sha256(TASK05_TEMPLATE)},
            },
            "materialized_files": [
                {"path": "eip.md", "content_sha256": sha256(eip_data)},
                {"path": "rubric.md", "content_sha256": sha256(rubric_view)},
                *[
                    {"path": item["package_path"], "content_sha256": item["content_sha256"]}
                    for item in supporting
                ],
            ],
            "preparation": {
                "script": rel(Path(__file__).resolve()),
                "script_sha256": file_sha256(Path(__file__).resolve()),
                "shared_task_05_engine": {
                    "script": rel(TASK05_ROOT / "scripts" / "prepare_inputs.py"),
                    "script_sha256": file_sha256(TASK05_ROOT / "scripts" / "prepare_inputs.py"),
                },
            },
        }
        manifest_path = package_dir / "manifest.yaml"
        write_bytes(manifest_path, yaml_bytes(manifest))
        populated = output_template(
            entry=entry,
            package_manifest_path=canonical_package / "manifest.yaml",
            package_manifest_sha=file_sha256(manifest_path),
            cohort=cohort,
            rubric=rubric,
            prompt_path=canonical_prompt,
            prompt_sha=sha256(prompt),
            assessment_sources=assessment_sources,
            primary=primary,
        )
        write_bytes(package_dir / "output-template.yaml", yaml_bytes(populated))
        print(
            f"prepared Hegota EIP-{number}: sources={len(assessment_sources)} "
            f"manifest={file_sha256(manifest_path)[:12]}"
        )
        prepared.append(number)
    return prepared


def package_inventory() -> dict[str, Any]:
    cohort, _, entries = approved_entries()
    packages: list[dict[str, Any]] = []
    for entry in entries:
        number = int(entry["eip"])
        package = PACKAGE_ROOT / f"eip-{number}"
        files = [
            {"path": path.relative_to(package).as_posix(), "content_sha256": file_sha256(path)}
            for path in sorted(item for item in package.rglob("*") if item.is_file())
        ]
        prompt = PROMPT_ROOT / f"eip-{number}.md"
        packages.append(
            {
                "eip": number,
                "package_path": rel(package),
                "manifest_sha256": file_sha256(package / "manifest.yaml"),
                "output_template_sha256": file_sha256(package / "output-template.yaml"),
                "prompt_path": rel(prompt),
                "prompt_sha256": file_sha256(prompt),
                "files": files,
            }
        )
    return {
        "schema_version": 1,
        "task_id": "08-hegota-prospective-complexity-assessment-package-freeze",
        "snapshot_id": cohort["snapshot_id"],
        "cohort_manifest": {"path": rel(COHORT_PATH), "content_sha256": file_sha256(COHORT_PATH)},
        "cohort_review": {"path": rel(REVIEW_PATH), "content_sha256": file_sha256(REVIEW_PATH)},
        "package_count": len(packages),
        "packages": packages,
    }


def compare_tree(expected: Path, regenerated: Path) -> None:
    expected_files = {
        path.relative_to(expected).as_posix(): file_sha256(path)
        for path in expected.rglob("*")
        if path.is_file()
    }
    actual_files = {
        path.relative_to(regenerated).as_posix(): file_sha256(path)
        for path in regenerated.rglob("*")
        if path.is_file()
    }
    if expected_files != actual_files:
        missing = sorted(set(expected_files) - set(actual_files))
        extra = sorted(set(actual_files) - set(expected_files))
        changed = sorted(
            path for path in set(expected_files) & set(actual_files)
            if expected_files[path] != actual_files[path]
        )
        raise InputError(
            f"Regeneration differs: missing={missing}, extra={extra}, changed={changed}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eips-repo", type=Path, default=package_engine.repo_default("EIPs"))
    parser.add_argument("--pm-repo", type=Path, default=package_engine.repo_default("pm"))
    parser.add_argument("--external-repo", action="append", default=[], metavar="REPOSITORY=PATH")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--verify-regeneration", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mapping = external_repo_map(args.external_repo)
    if args.prepare:
        build_packages(
            target_package_root=PACKAGE_ROOT,
            target_prompt_root=PROMPT_ROOT,
            eips_repo=args.eips_repo.resolve(),
            pm_repo=args.pm_repo.resolve(),
            external_repos=mapping,
            write_common_rubric=True,
        )
    elif args.freeze:
        write_bytes(PACKAGE_FREEZE, yaml_bytes(package_inventory()))
        print(f"froze package inventory: {PACKAGE_FREEZE}")
    else:
        with tempfile.TemporaryDirectory(prefix="hegota-package-regeneration-") as raw:
            temporary = Path(raw)
            build_packages(
                target_package_root=temporary / "packages",
                target_prompt_root=temporary / "prompts",
                eips_repo=args.eips_repo.resolve(),
                pm_repo=args.pm_repo.resolve(),
                external_repos=mapping,
                write_common_rubric=False,
            )
            compare_tree(PACKAGE_ROOT, temporary / "packages")
            compare_tree(PROMPT_ROOT, temporary / "prompts")
        expected = yaml_bytes(package_inventory())
        if not PACKAGE_FREEZE.is_file() or PACKAGE_FREEZE.read_bytes() != expected:
            raise InputError("Frozen package manifest is missing or not deterministic")
        print("verified byte-identical regeneration of all 37 packages and prompts")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as error:
        raise SystemExit(f"input error: {error}") from error
