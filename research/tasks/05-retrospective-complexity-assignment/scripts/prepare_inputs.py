#!/usr/bin/env python3
"""Build sealed Task 05 EIP packages and per-session wrapper prompts."""

from __future__ import annotations

import argparse
import copy
import hashlib
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK04_ROOT = REPO_ROOT / "research" / "tasks" / "04-complexity-assessment-ref-selection"
CONFIG_PATH = TASK_ROOT / "config.yaml"
TASK_CONTRACT = TASK_ROOT / "TASK.md"
OUTPUT_TEMPLATE = TASK_ROOT / "templates" / "output.yaml"

GITHUB_BLOB_RE = re.compile(
    r"https://github\.com/(?P<repository>[^/]+/[^/]+)/blob/"
    r"(?P<commit>[0-9a-f]{40})/(?P<path>[^)\s]+)"
)
RELATIVE_EIP_RE = re.compile(r"\]\(\./eip-(?P<number>\d+)\.md\)")
PROVENANCE_ONLY_REPOSITORIES = {
    "ethereum/execution-specs",
    "ethereum/execution-spec-tests",
}


class InputError(RuntimeError):
    """Raised when a source does not satisfy the sealed-input contract."""


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise InputError(f"Expected a YAML mapping: {path}")
    return data


def yaml_bytes(data: Any) -> bytes:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    ).encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes())


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return
    path.write_bytes(data)


def run_git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        env={**os.environ, "GIT_NO_LAZY_FETCH": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        message = result.stderr.decode(errors="replace").strip()
        raise InputError(f"git {' '.join(args)} failed in {repo}: {message}")
    return result.stdout


def git_blob(repo: Path, commit: str, path: str) -> tuple[bytes, str]:
    data = run_git(repo, "show", f"{commit}:{path}")
    blob = run_git(repo, "rev-parse", f"{commit}:{path}").decode().strip()
    return data, blob


def git_commit_time(repo: Path, commit: str) -> str:
    value = run_git(repo, "log", "-1", "--format=%cI", commit).decode().strip()
    return parse_datetime(value).isoformat().replace("+00:00", "Z")


def parse_datetime(value: str) -> datetime:
    if len(value) == 10:
        return datetime.fromisoformat(value).replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise InputError(f"Timestamp lacks a UTC offset: {value}")
    return parsed.astimezone(UTC)


def repo_default(name: str) -> Path:
    return REPO_ROOT.parent / name


def transform_rubric(source: bytes) -> bytes:
    text = source.decode()
    text = re.sub(
        r"Checklist revision: \*\*2\*\* \(28 anchors\) — see "
        r"\[Revision Notes\]\(#revision-notes\)",
        "Checklist revision: **2** (28 anchors)",
        text,
        count=1,
    )
    start = text.find("##### Revision Notes")
    end = text.find("\n## Consensus Specs", start)
    if start < 0 or end < 0:
        raise InputError("Pinned rubric no longer has the expected Revision Notes boundary")
    view = text[:start].rstrip() + "\n\n" + text[end + 1 :]
    if "Amsterdam calibration" in view or "proposed-anchors.md" in view:
        raise InputError("Retrospective calibration material leaked into the assessor view")
    return view.encode()


def prepare_rubric(pm_repo: Path, config: dict[str, Any]) -> dict[str, Any]:
    expected = config["rubric"]
    source, blob = git_blob(
        pm_repo,
        expected["repository_commit"],
        expected["path"],
    )
    if blob != expected["git_blob_sha"]:
        raise InputError(f"Rubric Git blob mismatch: {blob}")
    if sha256(source) != expected["content_sha256"]:
        raise InputError("Rubric content SHA-256 mismatch")

    assessor_view = transform_rubric(source)
    source_path = TASK_ROOT / "inputs" / "rubric" / "source.md"
    view_path = TASK_ROOT / "inputs" / "rubric" / "assessor-view.md"
    write_bytes(source_path, source)
    write_bytes(view_path, assessor_view)
    manifest = {
        "schema_version": 1,
        "source": copy.deepcopy(expected),
        "source_file": {
            "path": source_path.relative_to(REPO_ROOT).as_posix(),
            "content_sha256": sha256(source),
        },
        "assessor_view": {
            "path": view_path.relative_to(REPO_ROOT).as_posix(),
            "content_sha256": sha256(assessor_view),
            "transformation": "remove_revision_notes_and_calibration_examples_v1",
            "normative_criteria_preserved": True,
            "tier_definitions_preserved": True,
        },
    }
    write_bytes(
        TASK_ROOT / "inputs" / "rubric" / "manifest.yaml",
        yaml_bytes(manifest),
    )
    return manifest


def frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    boundary = text.find("\n---\n", 4)
    if boundary < 0:
        return {}
    data = yaml.safe_load(text[4:boundary])
    return data if isinstance(data, dict) else {}


def required_eips(text: str) -> set[int]:
    numbers = {int(item) for item in RELATIVE_EIP_RE.findall(text)}
    requires = frontmatter(text).get("requires", [])
    if isinstance(requires, int):
        numbers.add(requires)
    elif isinstance(requires, str):
        numbers.update(int(item) for item in re.findall(r"\d+", requires))
    elif isinstance(requires, list):
        numbers.update(int(item) for item in requires)
    return numbers


def external_repo_map(values: list[str]) -> dict[str, Path]:
    mapping: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise InputError(f"Expected REPOSITORY=PATH for --external-repo: {value}")
        repository, raw_path = value.split("=", 1)
        mapping[repository] = Path(raw_path).expanduser().resolve()
    default_consensus = repo_default("consensus-specs")
    if default_consensus.is_dir():
        mapping.setdefault("ethereum/consensus-specs", default_consensus)
    return mapping


def supporting_documents(
    *,
    eips_repo: Path,
    selected_commit: str,
    information_cutoff_at: str,
    eip_text: str,
    package_dir: Path,
    external_repos: dict[str, Path],
    provenance_only_repositories: set[str] | None = None,
    provenance_only_reason: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    provenance_only_links: list[dict[str, Any]] = []
    supporting_dir = package_dir / "supporting"

    excluded_repositories = (
        PROVENANCE_ONLY_REPOSITORIES
        if provenance_only_repositories is None
        else provenance_only_repositories
    )
    excluded_reason = provenance_only_reason or (
        "Task 04c excludes execution-spec and execution-spec-test "
        "artifacts from primary Task 05 evidence."
    )

    for number in sorted(required_eips(eip_text)):
        path = f"EIPS/eip-{number}.md"
        data, blob = git_blob(eips_repo, selected_commit, path)
        output = supporting_dir / f"eip-{number}.md"
        write_bytes(output, data)
        records.append(
            {
                "kind": "linked_eip",
                "repository": "ethereum/EIPs",
                "commit": selected_commit,
                "commit_time": git_commit_time(eips_repo, selected_commit),
                "path": path,
                "git_blob_sha": blob,
                "content_sha256": sha256(data),
                "immutable_url": (
                    f"https://github.com/ethereum/EIPs/blob/{selected_commit}/{path}"
                ),
                "package_path": output.relative_to(package_dir).as_posix(),
            }
        )

    seen_external: set[tuple[str, str, str]] = set()
    for match in GITHUB_BLOB_RE.finditer(eip_text):
        repository = match.group("repository")
        commit = match.group("commit")
        linked_path = match.group("path")
        path = linked_path.split("#", 1)[0].split("?", 1)[0]
        key = (repository, commit, path)
        if key in seen_external:
            continue
        seen_external.add(key)
        if repository == "ethereum/EIPs":
            continue
        if repository in excluded_repositories:
            provenance_only_links.append(
                {
                    "repository": repository,
                    "commit": commit,
                    "path": path,
                    "immutable_url": match.group(0),
                    "use": "provenance_only",
                    "reason": excluded_reason,
                }
            )
            continue
        if repository not in external_repos:
            raise InputError(
                f"Missing local repository for immutable supporting link {repository}; "
                f"pass --external-repo {repository}=/path/to/clone"
            )
        data, blob = git_blob(external_repos[repository], commit, path)
        commit_time = git_commit_time(external_repos[repository], commit)
        if parse_datetime(commit_time) > parse_datetime(information_cutoff_at):
            raise InputError(
                f"Supporting document postdates the information cutoff: {match.group(0)}"
            )
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{repository}--{path}")
        output = supporting_dir / safe_name
        write_bytes(output, data)
        records.append(
            {
                "kind": "immutable_external_link",
                "repository": repository,
                "commit": commit,
                "commit_time": commit_time,
                "path": path,
                "git_blob_sha": blob,
                "content_sha256": sha256(data),
                "immutable_url": match.group(0),
                "package_path": output.relative_to(package_dir).as_posix(),
            }
        )

    return records, provenance_only_links


def wrapper_text(fork_id: str, number: int) -> str:
    return f"""# Run one retrospective complexity assignment: {fork_id} EIP-{number}

This prompt is executed only inside the one-EIP isolated capsule at `/mnt/workspace`, using `gpt-5.6-sol` with reasoning effort `xhigh`.

Read `TASK.md` completely, then read `package/manifest.yaml`, `package/rubric.md`, `package/eip.md`, and every file listed under `assessment_source_files` in the manifest. Assess only {fork_id} EIP-{number}.

Do not browse the internet, invoke any skill, inspect project-management records, search for the hidden project repository, inspect another EIP, or read any file prohibited by the task contract. In particular, never use present-day implementation knowledge. If prohibited information is exposed, follow the contamination procedure.

Copy `package/output-template.yaml` to `assessment.yaml`. Preserve all populated provenance values, including `sources_consulted`, `operational_files_read`, and the isolated-launcher session fields. For every criterion, replace the evidence placeholder with one or more mappings containing `source`, `locator`, and `summary`; do not use scalar evidence strings. In `cross_eip_interactions`, record identified EIPs as bare integers such as `[5793]`, never strings such as `EIP-5793`. If the package describes an interaction without identifying its EIP number, preserve that uncertainty in `unidentified_interactions` rather than using later knowledge.

Do not run a repository validator, copy the result outside this capsule, or look for a completion checklist. Finish after writing `assessment.yaml`; the trusted launcher performs validation, collection, and checklist completion after this process exits.
"""


def populate_template(
    *,
    template: dict[str, Any],
    fork_id: str,
    record: dict[str, Any],
    package_manifest_path: Path,
    package_manifest_sha: str,
    rubric_manifest: dict[str, Any],
    prompt_path: Path,
    prompt_sha: str,
    assessment_source_files: list[str],
) -> dict[str, Any]:
    result = copy.deepcopy(template)
    selected = record["selection"]["selected_revision"]
    result["fork_id"] = fork_id
    result["eip"] = copy.deepcopy(record["eip"])
    result["provenance"]["input_package"] = {
        "manifest_path": package_manifest_path.relative_to(REPO_ROOT).as_posix(),
        "manifest_sha256": package_manifest_sha,
    }
    result["provenance"]["historical_eip"] = {
        "repository": selected["repository"],
        "commit": selected["commit"],
        "path": selected["path"],
        "committed_at": selected["committed_at"],
        "git_blob_sha": selected["git_blob_sha"],
        "content_sha256": selected["content_sha256"],
        "immutable_url": selected["immutable_url"],
        "information_cutoff_at": record["selection"]["information_cutoff_at"],
    }
    source = rubric_manifest["source"]
    result["provenance"]["rubric_source"] = {
        "repository": source["repository"],
        "commit": source["repository_commit"],
        "path": source["path"],
        "git_blob_sha": source["git_blob_sha"],
        "content_sha256": source["content_sha256"],
        "immutable_url": source["immutable_url"],
        "checklist_revision": source["checklist_revision"],
    }
    result["provenance"]["assessor_view"] = {
        "path": "rubric.md",
        "content_sha256": rubric_manifest["assessor_view"]["content_sha256"],
        "transformation": rubric_manifest["assessor_view"]["transformation"],
    }
    result["provenance"]["task_contract"] = {
        "path": TASK_CONTRACT.relative_to(REPO_ROOT).as_posix(),
        "content_sha256": file_sha256(TASK_CONTRACT),
    }
    result["provenance"]["session_prompt"] = {
        "path": prompt_path.relative_to(REPO_ROOT).as_posix(),
        "content_sha256": prompt_sha,
    }
    result["provenance"]["sources_consulted"] = copy.deepcopy(
        assessment_source_files
    )
    result["provenance"]["operational_files_read"] = [
        "PROMPT.md",
        "TASK.md",
        "package/manifest.yaml",
        "package/output-template.yaml",
    ]
    for criterion in result["criteria"]:
        criterion["evidence"] = [
            {
                "source": None,
                "locator": None,
                "summary": None,
            }
        ]
    return result


def prepare_eip(
    *,
    fork_id: str,
    ref_path: Path,
    eips_repo: Path,
    rubric_manifest: dict[str, Any],
    external_repos: dict[str, Path],
    output_template: dict[str, Any],
) -> None:
    record = load_yaml(ref_path)
    if record.get("fork_id") != fork_id:
        raise InputError(f"Fork mismatch in {ref_path}")
    if record.get("review", {}).get("status") != "approved":
        raise InputError(f"Task 04 ref is not approved: {ref_path}")

    number = int(record["eip"]["number"])
    completed_output = (
        TASK_ROOT / "outputs" / "fork-eips" / fork_id / f"eip-{number}.yaml"
    )
    if completed_output.is_file():
        print(f"skipped completed {fork_id} EIP-{number}: {completed_output}")
        return
    selected = record["selection"]["selected_revision"]
    eip_data, blob = git_blob(eips_repo, selected["commit"], selected["path"])
    if blob != selected["git_blob_sha"]:
        raise InputError(f"EIP-{number} Git blob mismatch")
    if sha256(eip_data) != selected["content_sha256"]:
        raise InputError(f"EIP-{number} content SHA-256 mismatch")

    package_dir = TASK_ROOT / "inputs" / "fork-eips" / fork_id / f"eip-{number}"
    write_bytes(package_dir / "eip.md", eip_data)
    rubric_data = (TASK_ROOT / "inputs" / "rubric" / "assessor-view.md").read_bytes()
    write_bytes(package_dir / "rubric.md", rubric_data)
    supporting, provenance_only_links = supporting_documents(
        eips_repo=eips_repo,
        selected_commit=selected["commit"],
        information_cutoff_at=record["selection"]["information_cutoff_at"],
        eip_text=eip_data.decode(),
        package_dir=package_dir,
        external_repos=external_repos,
    )

    manifest = {
        "schema_version": 1,
        "task_id": "05-retrospective-complexity-assignment",
        "fork_id": fork_id,
        "eip": copy.deepcopy(record["eip"]),
        "task_04_ref": {
            "path": ref_path.relative_to(REPO_ROOT).as_posix(),
            "content_sha256": file_sha256(ref_path),
            "review_status": "approved",
            "reviewed_at": record["review"]["reviewed_at"],
        },
        "historical_eip": {
            "package_path": "eip.md",
            "repository": selected["repository"],
            "commit": selected["commit"],
            "path": selected["path"],
            "committed_at": selected["committed_at"],
            "git_blob_sha": selected["git_blob_sha"],
            "content_sha256": selected["content_sha256"],
            "immutable_url": selected["immutable_url"],
            "information_cutoff_at": record["selection"]["information_cutoff_at"],
        },
        "rubric": {
            **copy.deepcopy(rubric_manifest["source"]),
            "package_path": "rubric.md",
            "assessor_view_sha256": rubric_manifest["assessor_view"]["content_sha256"],
            "transformation": rubric_manifest["assessor_view"]["transformation"],
        },
        "supporting_documents": supporting,
        "provenance_only_links": provenance_only_links,
        "assessment_source_files": [
            "eip.md",
            "rubric.md",
            *[item["package_path"] for item in supporting],
        ],
        "source_policy": {
            "internet_allowed": False,
            "follow_links_allowed": False,
            "files_outside_package_allowed": False,
            "dedicated_assessment_skill_allowed": False,
            "opportunistic_repository_evidence_allowed": False,
            "provenance_only_repositories": sorted(PROVENANCE_ONLY_REPOSITORIES),
        },
        "preparation": {
            "script": (Path(__file__).resolve().relative_to(REPO_ROOT).as_posix()),
            "script_sha256": file_sha256(Path(__file__).resolve()),
            "task_contract_sha256": file_sha256(TASK_CONTRACT),
        },
    }
    manifest_path = package_dir / "manifest.yaml"
    write_bytes(manifest_path, yaml_bytes(manifest))
    manifest_sha = file_sha256(manifest_path)

    prompt_path = TASK_ROOT / "prompts" / fork_id / f"eip-{number}.md"
    prompt_data = wrapper_text(fork_id, number).encode()
    write_bytes(prompt_path, prompt_data)

    populated = populate_template(
        template=output_template,
        fork_id=fork_id,
        record=record,
        package_manifest_path=manifest_path,
        package_manifest_sha=manifest_sha,
        rubric_manifest=rubric_manifest,
        prompt_path=prompt_path,
        prompt_sha=sha256(prompt_data),
        assessment_source_files=manifest["assessment_source_files"],
    )
    write_bytes(package_dir / "output-template.yaml", yaml_bytes(populated))
    print(
        f"prepared {fork_id} EIP-{number}: supporting={len(supporting)} "
        f"provenance_only_links={len(provenance_only_links)} "
        f"manifest={manifest_sha[:12]}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fork", required=True)
    parser.add_argument("--eip", action="append", type=int)
    parser.add_argument("--eips-repo", type=Path, default=repo_default("EIPs"))
    parser.add_argument("--pm-repo", type=Path, default=repo_default("pm"))
    parser.add_argument(
        "--external-repo",
        action="append",
        default=[],
        metavar="REPOSITORY=PATH",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_yaml(CONFIG_PATH)
    rubric_manifest = prepare_rubric(args.pm_repo.resolve(), config)
    refs = sorted(
        (TASK04_ROOT / "outputs" / "fork-eips" / args.fork).glob("eip-*.yaml")
    )
    if args.eip:
        wanted = set(args.eip)
        refs = [path for path in refs if int(path.stem.removeprefix("eip-")) in wanted]
        found = {int(path.stem.removeprefix("eip-")) for path in refs}
        if found != wanted:
            raise InputError(f"Missing Task 04 refs: {sorted(wanted - found)}")
    if not refs:
        raise InputError(f"No Task 04 refs found for {args.fork}")

    mapping = external_repo_map(args.external_repo)
    template = load_yaml(OUTPUT_TEMPLATE)
    for path in refs:
        prepare_eip(
            fork_id=args.fork,
            ref_path=path,
            eips_repo=args.eips_repo.resolve(),
            rubric_manifest=rubric_manifest,
            external_repos=mapping,
            output_template=template,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as error:
        raise SystemExit(f"input error: {error}") from error
