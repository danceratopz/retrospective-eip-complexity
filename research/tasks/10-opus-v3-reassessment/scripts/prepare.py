#!/usr/bin/env python3
"""Build the Task 10 v3 rubric view, historical package variants and Hegotá snapshot packages.

    prepare.py --eips-repo ../EIPs --pm-repo ../pm            # write
    prepare.py --eips-repo ../EIPs --pm-repo ../pm --check    # require byte-identical regeneration
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

import common
from common import (
    ASSESSMENT_CONTRACT,
    FORK_NAMES,
    RUBRIC_ROOT,
    SYSTEM_PROMPT,
    TASK_CONTRACT,
    TASK_ID,
    InputError,
    file_sha256,
    load_yaml,
    rel,
    sha256,
    yaml_bytes,
)
from engine_adapter import REPO_ROOT, TASK05_ROOT, TASK08_ROOT, TASK_ROOT, package_engine


RETRO_ROOT = TASK_ROOT / "retrospective"
PROSPECTIVE_ROOT = TASK_ROOT / "prospective"
COHORT_PATH = PROSPECTIVE_ROOT / "inputs" / "cohort.yaml"
REVIEW_PATH = PROSPECTIVE_ROOT / "inputs" / "cohort-review.yaml"
SECTIONS = {
    "EIPs Scheduled for Inclusion": "SFI",
    "Considered for Inclusion": "CFI",
    "Proposed for Inclusion": "PFI",
    "Declined for Inclusion": "DFI",
}
# Task 08's prospective evidence policy: consensus-spec documents stay provenance only.
PROVENANCE_ONLY_REPOSITORIES = {*package_engine.PROVENANCE_ONLY_REPOSITORIES, "ethereum/consensus-specs"}
OPERATIONAL_FILES = ["prompts/system.md", "prompts/assessment-contract.md"]

CHECK = False
MISMATCHES: list[str] = []


def write(path: Path, data: bytes) -> None:
    if CHECK:
        if not path.is_file() or path.read_bytes() != data:
            MISMATCHES.append(rel(path))
        return
    package_engine.write_bytes(path, data)


def operational_provenance() -> dict[str, Any]:
    return {
        "task_contract": {"path": rel(TASK_CONTRACT), "content_sha256": file_sha256(TASK_CONTRACT)},
        "system_prompt": {"path": rel(SYSTEM_PROMPT), "content_sha256": file_sha256(SYSTEM_PROMPT)},
        "assessment_contract": {
            "path": rel(ASSESSMENT_CONTRACT),
            "content_sha256": file_sha256(ASSESSMENT_CONTRACT),
        },
    }


def rubric_provenance(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    source = manifest["source"]
    rubric_source = {
        "repository": source["repository"],
        "commit": source["repository_commit"],
        "path": source["path"],
        "git_blob_sha": source["git_blob_sha"],
        "content_sha256": source["content_sha256"],
        "immutable_url": source["immutable_url"],
        "checklist_revision": source["checklist_revision"],
    }
    view = {
        "path": "rubric.md",
        "content_sha256": manifest["assessor_view"]["content_sha256"],
        "transformation": manifest["assessor_view"]["transformation"],
    }
    return rubric_source, view


def blank_template(task05_template: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(task05_template)
    result["task_id"] = TASK_ID
    assessor = result["provenance"]["assessor"]
    runtime = common.config()["runtime"]
    assessor["model"] = runtime["model"]
    assessor["reasoning_effort"] = runtime["effort"]
    for key in ("run_at", "session_id", "session_id_source", "isolation_method", "agent_identity"):
        assessor[key] = None
    for criterion in result["criteria"]:
        for key in ("score", "rationale", "confidence", "uncertainty_note", "exceptional_score_justification"):
            criterion[key] = None
        criterion["evidence"] = [{"source": None, "locator": None, "summary": None}]
        if criterion["id"] == common.XEIP:
            criterion.update(
                {
                    "base_score": None,
                    "bonus": None,
                    "interacting_eips": [],
                    "bonus_qualifying_eips": [],
                    "interaction_details": [],
                    "unidentified_interactions": [],
                }
            )
    result["totals"] = {"primary_score": None, "complexity_tier": None}
    for key, value in (("hindsight_control", None), ("information_control", None)):
        control = result.get(key)
        if control:
            control["attestation"] = value
    result["under_specification"]["criterion_ranges"] = []
    return result


def request_files(
    *,
    package_dir: Path,
    identity: str,
    documents: list[tuple[str, str, str]],
    sources: list[str],
    candidates: list[int],
    rubric_view: str,
    rubric: dict[str, Any],
) -> dict[str, Any]:
    prompt = common.render_prompt(
        identity=identity, documents=documents, rubric_view=rubric_view, candidates=candidates
    )
    schema = common.output_schema(rubric, sources, candidates)
    schema_data = common.schema_bytes(schema)
    write(package_dir / "schema.json", schema_data)
    return {
        "identity": identity,
        "documents": [{"path": path, "role": role} for path, role, _ in documents],
        "candidate_interacting_eips": candidates,
        "schema": {"path": "schema.json", "content_sha256": sha256(schema_data)},
        "prompt_sha256": sha256(prompt.encode()),
        "prompt_chars": len(prompt),
        "system_prompt_sha256": file_sha256(SYSTEM_PROMPT),
    }


def materialized(package_dir: Path, paths: list[str]) -> list[dict[str, str]]:
    return [{"path": path, "content_sha256": file_sha256(package_dir / path)} for path in paths]


# --- Rubric -------------------------------------------------------------------------------


def prepare_rubric(pm_repo: Path) -> tuple[str, dict[str, Any]]:
    source, view, manifest = common.rubric_material(pm_repo)
    write(RUBRIC_ROOT / "source.md", source)
    write(RUBRIC_ROOT / "assessor-view.md", view)
    write(RUBRIC_ROOT / "manifest.yaml", yaml_bytes(manifest))
    return view.decode(), manifest


# --- Historical packages ------------------------------------------------------------------


def prepare_retrospective(rubric_view: str, rubric_manifest: dict[str, Any]) -> int:
    settings = common.config()["retrospective"]
    task05_template = load_yaml(TASK05_ROOT / "templates" / "output.yaml")
    rubric_source, view_provenance = rubric_provenance(rubric_manifest)
    rubric = rubric_manifest["parsed"]
    count = 0
    for fork in settings["forks"]:
        base = settings["base_forks"][fork]
        for source_dir in sorted((TASK05_ROOT / "inputs" / "fork-eips" / fork).glob("eip-*")):
            source_manifest_path = source_dir / "manifest.yaml"
            source_manifest = load_yaml(source_manifest_path)
            number = int(source_manifest["eip"]["number"])
            package_dir = RETRO_ROOT / "inputs" / "packages" / fork / f"eip-{number}"
            reused = ["eip.md", *[item["package_path"] for item in source_manifest["supporting_documents"]]]
            expected_hashes = {"eip.md": source_manifest["historical_eip"]["content_sha256"]}
            expected_hashes |= {
                item["package_path"]: item["content_sha256"] for item in source_manifest["supporting_documents"]
            }
            documents = []
            for path in reused:
                data = (source_dir / path).read_bytes()
                if sha256(data) != expected_hashes[path]:
                    raise InputError(f"Task 05 {fork} EIP-{number} {path} no longer matches its manifest")
                write(package_dir / path, data)
                documents.append((path, "target" if path == "eip.md" else "supporting", data.decode()))
            write(package_dir / "rubric.md", rubric_view.encode())
            sources = list(source_manifest["assessment_source_files"])
            if sources != ["eip.md", "rubric.md", *reused[1:]]:
                raise InputError(f"Unexpected Task 05 source order for {fork} EIP-{number}")
            historical = source_manifest["historical_eip"]
            identity = (
                f"Target: {FORK_NAMES[fork]} EIP-{number} ({source_manifest['eip']['title']}), the historical "
                f"revision at ethereum/EIPs commit {historical['commit']}, selected for its information cutoff "
                f"{historical['information_cutoff_at']}. Judge only what this revision specifies; do not use "
                f"knowledge of the final design, its implementation or its outcome.\n"
                f"Assessment baseline: the {FORK_NAMES[base]} mainnet fork plus the changes this EIP requires, "
                f"including prerequisites proposed for {FORK_NAMES[fork]}."
            )
            candidates = common.candidate_eips(documents[0][2], number)
            request = request_files(
                package_dir=package_dir,
                identity=identity,
                documents=documents,
                sources=sources,
                candidates=candidates,
                rubric_view=rubric_view,
                rubric=rubric,
            )
            manifest = {
                "schema_version": 1,
                "task_id": TASK_ID,
                "mode": "retrospective",
                "fork_id": fork,
                "base_fork": base,
                "eip": copy.deepcopy(source_manifest["eip"]),
                "source_package": {
                    "task_id": source_manifest["task_id"],
                    "path": rel(source_dir),
                    "manifest_path": rel(source_manifest_path),
                    "manifest_sha256": file_sha256(source_manifest_path),
                    "reused_files": materialized(source_dir, reused),
                    "replaced_files": ["rubric.md", "output-template.yaml"],
                },
                "task_04_ref": copy.deepcopy(source_manifest["task_04_ref"]),
                "historical_eip": copy.deepcopy(historical),
                "rubric": {
                    **copy.deepcopy(rubric_manifest["source"]),
                    "package_path": "rubric.md",
                    "assessor_view_sha256": rubric_manifest["assessor_view"]["content_sha256"],
                    "transformation": rubric_manifest["assessor_view"]["transformation"],
                },
                "supporting_documents": copy.deepcopy(source_manifest["supporting_documents"]),
                "provenance_only_links": copy.deepcopy(source_manifest.get("provenance_only_links", [])),
                "assessment_source_files": sources,
                "source_policy": copy.deepcopy(source_manifest["source_policy"]),
                "request": request,
                "operational_files": operational_provenance(),
                "materialized_files": materialized(package_dir, [*sources, "schema.json"]),
                "preparation": {
                    "script": rel(Path(__file__)),
                    "script_sha256": file_sha256(Path(__file__)),
                    "shared_engine": rel(TASK_ROOT / "scripts" / "common.py"),
                    "shared_engine_sha256": file_sha256(TASK_ROOT / "scripts" / "common.py"),
                },
            }
            manifest_path = package_dir / "manifest.yaml"
            manifest_data = yaml_bytes(manifest)
            write(manifest_path, manifest_data)

            template = blank_template(task05_template)
            source_template = load_yaml(source_dir / "output-template.yaml")
            template["fork_id"] = fork
            template["eip"] = copy.deepcopy(source_template["eip"])
            provenance = template["provenance"]
            provenance["input_package"] = {"manifest_path": rel(manifest_path), "manifest_sha256": sha256(manifest_data)}
            provenance["source_package"] = {
                "manifest_path": rel(source_manifest_path),
                "manifest_sha256": file_sha256(source_manifest_path),
            }
            provenance["historical_eip"] = copy.deepcopy(source_template["provenance"]["historical_eip"])
            provenance["rubric_source"] = rubric_source
            provenance["assessor_view"] = view_provenance
            ops = operational_provenance()
            provenance["task_contract"] = ops["task_contract"]
            provenance["session_prompt"] = ops["assessment_contract"]
            provenance["system_prompt"] = ops["system_prompt"]
            provenance["sources_consulted"] = sources
            provenance["operational_files_read"] = OPERATIONAL_FILES
            ordered = {key: provenance[key] for key in [
                "input_package", "source_package", "historical_eip", "rubric_source", "assessor_view",
                "task_contract", "session_prompt", "system_prompt", "assessor", "sources_consulted",
                "operational_files_read",
            ]}  # fmt: skip
            template["provenance"] = ordered
            write(package_dir / "output-template.yaml", yaml_bytes(template))
            count += 1
    return count


# --- Hegotá snapshot ----------------------------------------------------------------------


def eip8081_lists(eips_repo: Path, commit: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data, blob = package_engine.git_blob(eips_repo, commit, "EIPS/eip-8081.md")
    section = None
    rows: list[dict[str, Any]] = []
    for line in data.decode().splitlines():
        heading = re.match(r"^### (.+)$", line)
        if heading:
            section = SECTIONS.get(heading.group(1).strip())
            continue
        item = re.match(r"^\* \[EIP-(\d+)\]\(\./eip-\d+\.md\): (.+)$", line)
        if item and section:
            rows.append({"eip": int(item.group(1)), "list": section, "listed_title": item.group(2).strip()})
    source = {
        "repository": "ethereum/EIPs",
        "repository_commit": commit,
        "committed_at": package_engine.git_commit_time(eips_repo, commit),
        "path": "EIPS/eip-8081.md",
        "git_blob_sha": blob,
        "content_sha256": sha256(data),
        "immutable_url": f"https://github.com/ethereum/EIPs/blob/{commit}/EIPS/eip-8081.md",
    }
    return source, rows


def prepare_cohort(eips_repo: Path) -> dict[str, Any]:
    settings = common.config()["prospective"]
    commit = settings["eips_commit"]
    source, rows = eip8081_lists(eips_repo, commit)
    if source["committed_at"] != settings["eips_committed_at"]:
        raise InputError("EIPs commit time differs from config")
    inventory = []
    for row in rows:
        if row["list"] not in settings["lists"]:
            continue
        path = f"EIPS/eip-{row['eip']}.md"
        data, _ = package_engine.git_blob(eips_repo, commit, path)
        meta = package_engine.frontmatter(data.decode())
        if meta.get("eip") != row["eip"]:
            raise InputError(f"EIP-{row['eip']} frontmatter number mismatch")
        inventory.append(
            {
                "eip": row["eip"],
                "eip_8081_list": row["list"],
                "path": path,
                "listed_title": row["listed_title"],
                "canonical_title": meta.get("title"),
                "eip_type": meta.get("type"),
                "category": meta.get("category"),
                "status": meta.get("status"),
            }
        )
    counts = {name: sum(1 for item in inventory if item["eip_8081_list"] == name) for name in settings["lists"]}
    cohort = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "snapshot_id": settings["snapshot_id"],
        "fork_id": settings["fork_id"],
        "meta_eip": settings["meta_eip"],
        "pulled_at": settings["eips_pulled_at"],
        "source": source,
        "selection": {
            "lists": settings["lists"],
            "excluded_lists": settings["excluded_lists"],
            "counts": counts,
            "declined_for_inclusion": [row["eip"] for row in rows if row["list"] == "DFI"],
        },
        "inventory": inventory,
    }
    write(COHORT_PATH, yaml_bytes(cohort))
    return cohort


def approved_review(cohort: dict[str, Any]) -> list[dict[str, Any]]:
    review = load_yaml(REVIEW_PATH)
    entries = review.get("entries", [])
    if [item["eip"] for item in entries] != [item["eip"] for item in cohort["inventory"]]:
        raise InputError("Cohort-review order differs from the cohort inventory")
    for entry, item in zip(entries, cohort["inventory"]):
        if entry["eip_8081_list"] != item["eip_8081_list"] or entry["canonical_title"] != item["canonical_title"]:
            raise InputError(f"EIP-{entry['eip']} review differs from the cohort inventory")
        if entry["disposition"] not in {"score_el_rubric", "not_applicable_to_el_rubric"}:
            raise InputError(f"EIP-{entry['eip']} has no disposition")
    return entries


def prepare_prospective(
    eips_repo: Path, external_repos: dict[str, Path], rubric_view: str, rubric_manifest: dict[str, Any]
) -> int:
    settings = common.config()["prospective"]
    cohort = prepare_cohort(eips_repo)
    entries = approved_review(cohort)
    commit = settings["eips_commit"]
    cutoff = settings["eips_committed_at"]
    rubric_source, view_provenance = rubric_provenance(rubric_manifest)
    rubric = rubric_manifest["parsed"]
    task08_template = load_yaml(
        TASK08_ROOT / "inputs" / "packages" / "hegota-pfi-2026-08-26" / "eip-2488" / "output-template.yaml"
    )
    count = 0
    for entry in entries:
        if entry["disposition"] != "score_el_rubric":
            continue
        number = int(entry["eip"])
        path = f"EIPS/eip-{number}.md"
        package_dir = PROSPECTIVE_ROOT / "inputs" / "packages" / settings["namespace"] / f"eip-{number}"
        data, blob = package_engine.git_blob(eips_repo, commit, path)
        write(package_dir / "eip.md", data)
        write(package_dir / "rubric.md", rubric_view.encode())
        supporting, provenance_only, unavailable = snapshot_supporting(
            eips_repo, commit, cutoff, data.decode(), package_dir, external_repos
        )
        sources = ["eip.md", "rubric.md", *[item["package_path"] for item in supporting]]
        documents = [("eip.md", "target", data.decode())] + [
            (item["package_path"], "supporting", (package_dir / item["package_path"]).read_text(encoding="utf-8"))
            for item in supporting
        ]
        identity = (
            f"Target: EIP-{number} ({entry['canonical_title']}) at ethereum/EIPs commit {commit} "
            f"({cutoff}), a candidate for the {FORK_NAMES['hegota']} fork.\n"
            f"Assessment baseline: the {FORK_NAMES[settings['base_fork']]} mainnet fork plus the changes this "
            f"EIP requires, including prerequisites proposed for {FORK_NAMES['hegota']}."
        )
        if unavailable:
            identity += "\nReferenced but not supplied (not in ethereum/EIPs at this commit): " + ", ".join(
                f"EIP-{item}" for item in unavailable
            ) + "."
        candidates = common.candidate_eips(data.decode(), number)
        request = request_files(
            package_dir=package_dir, identity=identity, documents=documents, sources=sources,
            candidates=candidates, rubric_view=rubric_view, rubric=rubric,
        )  # fmt: skip
        snapshot_eip = {
            "package_path": "eip.md",
            "repository": "ethereum/EIPs",
            "commit": commit,
            "path": path,
            "committed_at": cutoff,
            "git_blob_sha": blob,
            "content_sha256": sha256(data),
            "immutable_url": f"https://github.com/ethereum/EIPs/blob/{commit}/{path}",
            "information_cutoff_at": cutoff,
        }
        manifest = {
            "schema_version": 1,
            "task_id": TASK_ID,
            "mode": "prospective",
            "fork_id": "hegota",
            "base_fork": settings["base_fork"],
            "snapshot_id": settings["snapshot_id"],
            "eip_8081_list": entry["eip_8081_list"],
            "eip": {"number": number, "title": entry["canonical_title"], "layers": list(entry["affected_layers"])},
            "cohort_manifest": {"path": rel(COHORT_PATH), "content_sha256": file_sha256(COHORT_PATH)},
            "cohort_review": {
                "path": rel(REVIEW_PATH),
                "content_sha256": file_sha256(REVIEW_PATH),
                "disposition": entry["disposition"],
                "review_status": entry["review"]["status"],
            },
            "snapshot_eip": snapshot_eip,
            "rubric": {
                **copy.deepcopy(rubric_manifest["source"]),
                "package_path": "rubric.md",
                "assessor_view_sha256": rubric_manifest["assessor_view"]["content_sha256"],
                "transformation": rubric_manifest["assessor_view"]["transformation"],
            },
            "supporting_documents": supporting,
            "provenance_only_links": provenance_only,
            "unavailable_linked_eips": unavailable,
            "assessment_source_files": sources,
            "source_policy": {
                "internet_allowed": False,
                "follow_links_allowed": False,
                "files_outside_package_allowed": False,
                "dedicated_assessment_skill_allowed": False,
                "opportunistic_repository_evidence_allowed": False,
                "post_snapshot_information_allowed": False,
                "provenance_only_repositories": sorted(PROVENANCE_ONLY_REPOSITORIES),
            },
            "request": request,
            "operational_files": operational_provenance(),
            "materialized_files": materialized(package_dir, [*sources, "schema.json"]),
            "preparation": {
                "script": rel(Path(__file__)),
                "script_sha256": file_sha256(Path(__file__)),
                "shared_engine": rel(TASK_ROOT / "scripts" / "common.py"),
                "shared_engine_sha256": file_sha256(TASK_ROOT / "scripts" / "common.py"),
                "package_policy": "Task 08 prospective package policy, through the Task 05 supporting_documents engine",
            },
        }
        manifest_path = package_dir / "manifest.yaml"
        manifest_data = yaml_bytes(manifest)
        write(manifest_path, manifest_data)

        template = copy.deepcopy(task08_template)
        template.pop("snapshot_id")
        template = blank_template(template)
        template["fork_id"] = "hegota"
        template = {
            key: template[key] for key in ["schema_version", "task_id", "fork_id"]
        } | {"snapshot_id": settings["snapshot_id"], "eip_8081_list": entry["eip_8081_list"]} | {
            key: value for key, value in template.items() if key not in {"schema_version", "task_id", "fork_id"}
        }
        template["eip"] = copy.deepcopy(manifest["eip"])
        ops = operational_provenance()
        template["provenance"] = {
            "input_package": {"manifest_path": rel(manifest_path), "manifest_sha256": sha256(manifest_data)},
            "cohort_snapshot": {
                "snapshot_id": settings["snapshot_id"],
                "manifest_path": rel(COHORT_PATH),
                "manifest_sha256": file_sha256(COHORT_PATH),
                "pulled_at": settings["eips_pulled_at"],
                "repository": "ethereum/EIPs",
                "commit": commit,
                "committed_at": cutoff,
                "information_cutoff_at": cutoff,
                "eip_8081_list": entry["eip_8081_list"],
            },
            "snapshot_eip": snapshot_eip,
            "rubric_source": rubric_source,
            "assessor_view": view_provenance,
            "task_contract": ops["task_contract"],
            "assessment_contract": ops["assessment_contract"],
            "session_prompt": ops["assessment_contract"],
            "system_prompt": ops["system_prompt"],
            "assessor": template["provenance"]["assessor"],
            "sources_consulted": sources,
            "operational_files_read": OPERATIONAL_FILES,
        }
        write(package_dir / "output-template.yaml", yaml_bytes(template))
        count += 1
    return count


def snapshot_supporting(
    eips_repo: Path, commit: str, cutoff: str, text: str, package_dir: Path, external_repos: dict[str, Path]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[int]]:
    """Task 05's supporting_documents at the snapshot, recording linked EIPs absent from the EIPs repository.

    The engine has no unavailable-document path, so it is given a link list of the
    available linked EIPs (as `requires`) plus the target's immutable external links.
    """
    linked = sorted(package_engine.required_eips(text))
    present = set(
        package_engine.run_git(eips_repo, "ls-tree", "--name-only", commit, "EIPS/").decode().split()
    )
    available = [n for n in linked if f"EIPS/eip-{n}.md" in present]
    unavailable = [n for n in linked if n not in available]
    links = [match.group(0) for match in package_engine.GITHUB_BLOB_RE.finditer(text)]
    discovery = f"---\nrequires: {', '.join(map(str, available))}\n---\n" + "\n".join(links) + "\n"
    target = package_dir
    if CHECK:
        target = TASK_ROOT / ".check-scratch"
    supporting, provenance_only = package_engine.supporting_documents(
        eips_repo=eips_repo, selected_commit=commit, information_cutoff_at=cutoff,
        eip_text=discovery, package_dir=target, external_repos=external_repos,
        provenance_only_repositories=PROVENANCE_ONLY_REPOSITORIES,
        provenance_only_reason=PROVENANCE_REASON,
    )  # fmt: skip
    if CHECK:
        for item in supporting:
            write(package_dir / item["package_path"], (target / item["package_path"]).read_bytes())
        for leftover in sorted(target.rglob("*"), reverse=True):
            leftover.unlink() if leftover.is_file() else leftover.rmdir()
        target.rmdir() if target.exists() else None
    return supporting, provenance_only, unavailable


PROVENANCE_REASON = (
    "Task 10 follows Task 08: implementation and test repositories and, for cross-layer proposals, "
    "consensus-spec documents stay out of execution-layer scoring evidence."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eips-repo", type=Path, required=True)
    parser.add_argument("--pm-repo", type=Path, required=True)
    parser.add_argument("--external-repo", action="append", default=[], metavar="REPOSITORY=PATH")
    parser.add_argument("--check", action="store_true", help="Require byte-identical regeneration")
    return parser.parse_args()


def main() -> int:
    global CHECK
    args = parse_args()
    CHECK = args.check
    view, manifest = prepare_rubric(args.pm_repo.resolve())
    retro = prepare_retrospective(view, manifest)
    prospective = prepare_prospective(
        args.eips_repo.resolve(), package_engine.external_repo_map(args.external_repo), view, manifest
    )
    if CHECK:
        if MISMATCHES:
            raise InputError(f"Regeneration differs: {json.dumps(MISMATCHES, indent=1)}")
        print(f"verified byte-identical regeneration: {retro} historical and {prospective} Hegotá packages")
    else:
        print(f"prepared {retro} historical and {prospective} Hegotá packages")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as error:
        raise SystemExit(f"input error: {error}") from error
