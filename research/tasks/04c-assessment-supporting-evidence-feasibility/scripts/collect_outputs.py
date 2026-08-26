#!/usr/bin/env python3
"""Collect deterministic Task 04c repository snapshots and evidence records."""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


TASK_ID = "04c-assessment-supporting-evidence-feasibility"
TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK04_ROOT = (
    REPO_ROOT
    / "research/tasks/04-complexity-assessment-ref-selection/outputs/fork-eips"
)
FORKS = ("shanghai", "cancun", "prague", "osaka", "amsterdam")
REPOSITORIES = {
    "execution_specs": {
        "name": "ethereum/execution-specs",
        "path": Path("/home/dtopz/code/github/execution-specs"),
        "base_ref": "origin/forks/amsterdam",
        "github": "https://github.com/ethereum/execution-specs",
    },
    "execution_spec_tests": {
        "name": "ethereum/execution-spec-tests",
        "path": Path("/home/dtopz/code/github/execution-spec-tests"),
        "base_ref": "origin/main",
        "github": "https://github.com/ethereum/execution-spec-tests",
    },
}
MATURITY = {
    "absent",
    "reference_only",
    "scaffold",
    "partial",
    "substantively_informative",
    "uncertain",
}
METHOD_USE = {
    "exclude",
    "provenance_only",
    "uncertainty_context",
    "supplementary_candidate",
    "primary_candidate",
}


def git(repo: Path, *args: str, check: bool = True, text: bool = True) -> Any:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=text,
    )
    if text:
        return result.stdout.rstrip("\n")
    return result.stdout


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected YAML mapping: {path}")
    return value


def dump_yaml(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )


def normalized_cutoff(value: str) -> str:
    if len(value) == 10:
        return f"{value}T00:00:00Z"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RuntimeError(f"cutoff lacks timezone: {value}")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise RuntimeError(f"timestamp lacks timezone: {value}")
    return parsed.astimezone(UTC)


def exact_search(repo: Path, snapshot: str, number: int) -> dict[str, Any]:
    names = git(repo, "ls-tree", "-r", "--name-only", snapshot).splitlines()
    path_pattern = re.compile(rf"(?i)eip[-_ ]?{number}(?:\D|$)")
    path_hits = sorted(path for path in names if path_pattern.search(path))
    content_pattern = rf"eip[-_ /]?{number}([^0-9]|$)"
    grep = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "grep",
            "-I",
            "-i",
            "-l",
            "-E",
            content_pattern,
            snapshot,
            "--",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    prefix = f"{snapshot}:"
    content_hits = sorted(
        line.removeprefix(prefix)
        for line in grep.stdout.splitlines()
        if line.startswith(prefix)
    )
    subject_pattern = rf"eip[- ]*{number}([^0-9]|$)"
    subject_lines = git(
        repo,
        "log",
        snapshot,
        "--regexp-ignore-case",
        f"--grep={subject_pattern}",
        "--extended-regexp",
        "--format=%H%x09%cI%x09%s",
    ).splitlines()
    subject_hits = []
    for line in subject_lines:
        fields = line.split("\t", 2)
        if len(fields) == 3:
            subject_hits.append(
                {"commit": fields[0], "committed_at": fields[1], "subject": fields[2]}
            )
    return {
        "scope": "entire snapshot tree and reachable commit subjects through the snapshot",
        "path_pattern": rf"(?i)eip[-_ ]?{number}(?:\D|$)",
        "content_pattern": rf"(?i){content_pattern}",
        "commit_subject_pattern": rf"(?i){subject_pattern}",
        "path_hits": path_hits,
        "content_hits": content_hits,
        "commit_subject_hits": subject_hits,
    }


def blob_record(
    repository: dict[str, Any], snapshot: str, path: str, relevance: str
) -> dict[str, Any]:
    repo = repository["path"]
    blob_sha = git(repo, "rev-parse", f"{snapshot}:{path}")
    content = git(repo, "cat-file", "blob", f"{snapshot}:{path}", text=False)
    changed = git(
        repo,
        "log",
        "-1",
        "--format=%H%x09%cI%x09%s",
        snapshot,
        "--",
        path,
    ).split("\t", 2)
    if len(changed) != 3:
        raise RuntimeError(f"cannot resolve last change for {snapshot}:{path}")
    return {
        "path": path,
        "commit": snapshot,
        "git_blob_sha": blob_sha,
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "last_changed_commit": changed[0],
        "last_changed_at": changed[1],
        "last_changed_subject": changed[2],
        "immutable_url": f'{repository["github"]}/blob/{snapshot}/{path}',
        "relevance": relevance,
    }


EVIDENCE: dict[tuple[str, int, str], dict[str, Any]] = {
    ("cancun", 1153, "execution_specs"): {
        "maturity": "reference_only",
        "use": "provenance_only",
        "gain": "minimal",
        "paths": ["network-upgrades/mainnet-upgrades/shanghai.md"],
        "rationale": "The snapshot names EIP-1153 only in a legacy network-upgrade tracker. It contains no EELS behavior or EIP-specific tests and is outside the candidate specification/test construct.",
        "gain_summary": "It documents that the proposal was tracked, but adds no proposal behavior beyond the historical EIP text.",
        "risks": ["The tracker concerns fork and client status rather than the proposal's technical complexity."],
        "confidence": "high",
        "unknowns": [],
    },
    ("cancun", 4844, "execution_specs"): {
        "maturity": "reference_only",
        "use": "provenance_only",
        "gain": "minimal",
        "paths": ["network-upgrades/mainnet-upgrades/shanghai.md"],
        "rationale": "The snapshot names EIP-4844 only in a legacy Shanghai upgrade tracker. No EELS Cancun module or EIP-specific test source is present at the Cancun cutoff.",
        "gain_summary": "The tracker records historical attention but does not clarify the selected EIP's implementation surface.",
        "risks": ["Exposing an implementation-status tracker would import process and client-status evidence outside Task 05's proposal-time construct."],
        "confidence": "high",
        "unknowns": [],
    },
    ("prague", 2537, "execution_specs"): {
        "maturity": "reference_only",
        "use": "provenance_only",
        "gain": "minimal",
        "paths": [
            "network-upgrades/client-integration-testnets/YOLOv2.md",
            "network-upgrades/retrospectives/berlin.md",
        ],
        "rationale": "The only matches are old network-upgrade and retrospective documents. They name EIP-2537 but contain no Prague-cutoff EELS behavior or EIP-specific tests.",
        "gain_summary": "The references establish earlier protocol history, not additional proposal-time technical detail.",
        "risks": ["A retrospective document is hindsight-bearing and must never be shown to an assessor."],
        "confidence": "high",
        "unknowns": [],
    },
    ("osaka", 7939, "execution_spec_tests"): {
        "maturity": "partial",
        "use": "provenance_only",
        "gain": "material",
        "paths": [
            "tests/osaka/eip7939_count_leading_zeros/spec.py",
            "tests/osaka/eip7939_count_leading_zeros/test_count_leading_zeros.py",
        ],
        "rationale": "The snapshot has meaningful CLZ value, gas, stack-underflow, jump-context, and fork-transition tests. Its declared REFERENCE_SPEC_VERSION is c8321494fdfbfda52ad46c3515a7ca5dc86b857c, which resolves locally to the EIP-7823 blob rather than EIP-7939 or the approved Task 04 blob, so the suite is not a clean version-bound representation of the selected proposal.",
        "gain_summary": "The cases reveal a broad behavioral test surface beyond the EIP prose, but the broken specification binding prevents safe scoring use.",
        "risks": [
            "The tests encode already-designed edge cases and work completed before the proposal cutoff.",
            "The incorrect reference-spec binding makes alignment with the approved historical EIP revision unverifiable from the suite metadata.",
        ],
        "confidence": "high",
        "unknowns": ["Whether the incorrect version value was a temporary copy error or reflected an unresolved test-publication workflow is not established locally."],
        "reference_spec_binding": {
            "declared_git_path": "EIPS/eip-7939.md",
            "declared_git_blob_sha": "c8321494fdfbfda52ad46c3515a7ca5dc86b857c",
            "resolved_object_path": "EIPS/eip-7823.md",
            "matches_task04_selected_blob": False,
        },
    },
    ("osaka", 7951, "execution_spec_tests"): {
        "maturity": "partial",
        "use": "provenance_only",
        "gain": "material",
        "paths": [
            "tests/osaka/eip7951_p256verify_precompiles/conftest.py",
            "tests/osaka/eip7951_p256verify_precompiles/helpers.py",
            "tests/osaka/eip7951_p256verify_precompiles/spec.py",
            "tests/osaka/eip7951_p256verify_precompiles/test_p256verify.py",
            "tests/osaka/eip7951_p256verify_precompiles/test_p256verify_before_fork.py",
            "tests/osaka/eip7951_p256verify_precompiles/vectors/secp256r1_test.json",
        ],
        "rationale": "The snapshot contains substantial valid, invalid, gas, call-context, entry-point, vector, and pre-fork coverage. The tests predate the selected EIP's creation commit and declare REFERENCE_SPEC_VERSION 06aadd458ee04ede80498db55927b052eb5bef38, which resolves locally to the EIP-2935 blob rather than EIP-7951 or the approved Task 04 blob.",
        "gain_summary": "The suite exposes a large realized test surface, but it is not safely bound to the selected proposal revision and predates that public EIP blob.",
        "risks": [
            "The evidence reveals implementation and testing work already completed before the selected EIP was published.",
            "The incorrect reference-spec binding can encode decisions from a draft or branch that is not the approved historical EIP text.",
        ],
        "confidence": "high",
        "unknowns": ["The exact unpublished design source used to write the pre-creation tests is not identifiable from the default-branch snapshot."],
        "reference_spec_binding": {
            "declared_git_path": "EIPS/eip-7951.md",
            "declared_git_blob_sha": "06aadd458ee04ede80498db55927b052eb5bef38",
            "resolved_object_path": "EIPS/eip-2935.md",
            "matches_task04_selected_blob": False,
        },
    },
    ("amsterdam", 7610, "execution_specs"): {
        "maturity": "substantively_informative",
        "use": "provenance_only",
        "gain": "material",
        "paths": [
            "README.md",
            "src/ethereum/forks/osaka/state.py",
            "src/ethereum/forks/osaka/vm/instructions/system.py",
            "src/ethereum/forks/osaka/vm/interpreter.py",
        ],
        "rationale": "The snapshot contains an implementation ported in December 2024: a storage-existence predicate and collision checks in opcode-level and transaction-level creation paths. It materially demonstrates the implementation surface, but that is realized work rather than complexity visible only from the selected EIP proposal.",
        "gain_summary": "The blobs clarify that the rule touches state inspection and both CREATE and transaction-creation collision paths.",
        "risks": [
            "Showing completed executable specification code can bias difficulty downward by presenting a finished solution.",
            "The change was applied across historical fork modules, which exposes repository architecture and completed porting breadth not stated by the proposal.",
        ],
        "confidence": "high",
        "unknowns": ["The local default-branch history does not establish why this implementation preceded Amsterdam proposal status by roughly nine months."],
    },
    ("amsterdam", 8282, "execution_specs"): {
        "maturity": "substantively_informative",
        "use": "supplementary_candidate",
        "gain": "material",
        "paths": [
            "packages/testing/src/execution_testing/forks/forks/eips/amsterdam/eip_8282.py",
            "src/ethereum/forks/amsterdam/fork.py",
            "src/ethereum/forks/amsterdam/requests.py",
            "tests/amsterdam/eip8282_builder_execution_requests/builder_deposit_factory_deploy.json",
            "tests/amsterdam/eip8282_builder_execution_requests/builder_exit_factory_deploy.json",
            "tests/amsterdam/eip8282_builder_execution_requests/conftest.py",
            "tests/amsterdam/eip8282_builder_execution_requests/helpers.py",
            "tests/amsterdam/eip8282_builder_execution_requests/spec.py",
            "tests/amsterdam/eip8282_builder_execution_requests/test_builder_deposit_disable.py",
            "tests/amsterdam/eip8282_builder_execution_requests/test_builder_deposits.py",
            "tests/amsterdam/eip8282_builder_execution_requests/test_builder_exit_disable.py",
            "tests/amsterdam/eip8282_builder_execution_requests/test_builder_exits.py",
            "tests/amsterdam/eip8282_builder_execution_requests/test_builder_requests_during_fork.py",
            "tests/amsterdam/eip8282_builder_execution_requests/test_builder_requests_out_of_gas.py",
            "tests/amsterdam/eip8282_builder_execution_requests/test_contract_deployment.py",
            "tests/amsterdam/eip8282_builder_execution_requests/test_eip_mainnet.py",
            "tests/amsterdam/eip8282_builder_execution_requests/test_modified_builder_contract.py",
        ],
        "rationale": "The cutoff snapshot contains executable specification logic, fork configuration, contract artifacts, and tests for request limits, invalid inputs, fees, disable/reset behavior, transition behavior, out-of-gas handling, deployment, and mainnet state. The suite pins git blob 35ab20cb31a416c50600da00125d262e1756850c, exactly matching the approved Task 04 EIP blob.",
        "gain_summary": "The allowlisted blobs materially clarify integration points and edge-case surface beyond the proposal text while remaining contemporaneous and version-bound.",
        "risks": [
            "The code and tests were already implemented before the proposal cutoff, so exposure measures a proposal-plus-realized-solution construct.",
            "A full repository checkout would expose unrelated Amsterdam and post-merge test work; only exact blobs are admissible for a sensitivity run.",
        ],
        "confidence": "high",
        "unknowns": ["A sensitivity run is needed to measure whether the artifact changes scores or only confidence and under-specification notes."],
        "reference_spec_binding": {
            "declared_git_path": "EIPS/eip-8282.md",
            "declared_git_blob_sha": "35ab20cb31a416c50600da00125d262e1756850c",
            "resolved_object_path": "EIPS/eip-8282.md",
            "matches_task04_selected_blob": True,
        },
    },
}


def relevance(path: str) -> str:
    name = Path(path).name
    if path == "README.md":
        return "Repository-level EIP reference and activation table entry."
    if "network-upgrades" in path:
        return "Historical network-upgrade document that names the EIP."
    if name == "state.py":
        return "State predicate used to detect non-empty storage."
    if name == "system.py":
        return "Opcode-level contract creation collision handling."
    if name == "interpreter.py":
        return "Transaction-level contract creation collision handling."
    if name == "fork.py":
        return "Executable fork processing and system-request integration."
    if name == "requests.py":
        return "Executable request types and request serialization behavior."
    if name == "spec.py":
        return "Test-suite constants, helpers, and declared historical EIP binding."
    if name == "conftest.py":
        return "EIP-specific fixtures and parametrized setup."
    if name == "helpers.py":
        return "EIP-specific request or vector construction helpers."
    if name.endswith(".json"):
        return "EIP-specific contract artifact or cryptographic test vector."
    if name.startswith("test_"):
        return f"EIP-specific behavioral coverage in {name}."
    if "eip_8282.py" in path:
        return "Testing-fork configuration for EIP-8282."
    return "EIP-specific historical source inspected for maturity."


def repository_record() -> dict[str, Any]:
    records: dict[str, Any] = {}
    for repository_id, repository in REPOSITORIES.items():
        repo = repository["path"]
        base_ref = repository["base_ref"]
        remotes = []
        remote_lines = git(repo, "remote", "-v").splitlines()
        for line in remote_lines:
            fields = line.split()
            if len(fields) >= 3:
                remotes.append(
                    {
                        "name": fields[0],
                        "url": fields[1],
                        "direction": fields[2].strip("()"),
                    }
                )
        first_parent = git(repo, "rev-list", "--first-parent", "--reverse", base_ref).splitlines()[0]
        missing = [
            line
            for line in git(repo, "rev-list", "--objects", "--missing=print", base_ref).splitlines()
            if line.startswith("?")
        ]
        promisor = git(repo, "config", "--get", "remote.origin.promisor", check=False)
        partial_filter = git(
            repo, "config", "--get", "remote.origin.partialclonefilter", check=False
        )
        fsck = subprocess.run(
            ["git", "-C", str(repo), "fsck", "--connectivity-only", "--no-dangling"],
            check=False,
            capture_output=True,
            text=True,
        )
        if fsck.returncode != 0:
            raise RuntimeError(f"Git connectivity check failed for {repo}: {fsck.stderr}")
        records[repository_id] = {
            "repository": repository["name"],
            "local_path": str(repo),
            "origin_url": git(repo, "remote", "get-url", "origin"),
            "remotes": remotes,
            "local_head_ref": git(repo, "symbolic-ref", "-q", "HEAD"),
            "remote_default_ref": git(repo, "symbolic-ref", "refs/remotes/origin/HEAD"),
            "base_ref": base_ref,
            "current_head": git(repo, "rev-parse", "HEAD"),
            "base_ref_head": git(repo, "rev-parse", base_ref),
            "object_format": git(repo, "rev-parse", "--show-object-format"),
            "shallow": git(repo, "rev-parse", "--is-shallow-repository") == "true",
            "partial": promisor.lower() == "true" or bool(partial_filter),
            "promisor": promisor or None,
            "partial_clone_filter": partial_filter or None,
            "first_parent_root_commit": first_parent,
            "first_parent_root_committed_at": git(
                repo, "show", "-s", "--format=%cI", first_parent
            ),
            "earliest_required_cutoff": "2022-02-04T00:00:00Z",
            "history_covers_required_cutoffs": parse_instant(
                git(repo, "show", "-s", "--format=%cI", first_parent)
            )
            <= parse_instant("2022-02-04T00:00:00Z"),
            "missing_reachable_objects": missing,
            "connectivity_check": {
                "command": f"git -C {repo} fsck --connectivity-only --no-dangling",
                "result": "pass" if fsck.returncode == 0 else "fail",
                "output": (fsck.stdout + fsck.stderr).strip() or None,
            },
        }
    return {
        "schema_version": 1,
        "task_id": TASK_ID,
        "collected_at": "2026-08-25",
        "snapshot_policy": {
            "timestamp_basis": "committer time",
            "date_only_normalization": "00:00:00Z",
            "traversal": "first-parent default-branch lineage",
            "reason": "execution-specs imports EEST history through merge parents; unrestricted traversal can select an EEST-side commit that was never the execution-specs default-branch state at the cutoff.",
        },
        "repositories": records,
        "migration_history": [
            {
                "event": "EEST added to EELS as a submodule",
                "repository": "ethereum/execution-specs",
                "commit": "0bcb94511009d5f07ca805d2a44b3a97b08edaca",
                "committed_at": "2025-07-24T12:14:42-04:00",
                "path": "eest_tests/execution-spec-tests",
                "gitlink_commit": "6cf5107cee0eae1c2d4dd6a5ef5bc729aea6c379",
                "immutable_url": "https://github.com/ethereum/execution-specs/commit/0bcb94511009d5f07ca805d2a44b3a97b08edaca",
            },
            {
                "event": "EEST test sources imported into EELS as a Git subtree",
                "repository": "ethereum/execution-specs",
                "commit": "4d94a805d7a4c76a5945458922a6e2a0d868ddb0",
                "committed_at": "2025-08-25T10:20:46+02:00",
                "path": "tests/eest",
                "subtree_split": "e1e722807359ac01dc22c3d23e5de36ec675b3b1",
                "immutable_url": "https://github.com/ethereum/execution-specs/commit/4d94a805d7a4c76a5945458922a6e2a0d868ddb0",
            },
            {
                "event": "EEST submodule removed after subtree import",
                "repository": "ethereum/execution-specs",
                "commit": "1e7a52c9fb46e391090d4ee55fe3024b7f6e88ef",
                "committed_at": "2025-08-25T10:33:26+02:00",
                "path": "eest_tests/execution-spec-tests",
                "immutable_url": "https://github.com/ethereum/execution-specs/commit/1e7a52c9fb46e391090d4ee55fe3024b7f6e88ef",
            },
            {
                "event": "EEST sources moved into their EELS package during weld preparation",
                "repository": "ethereum/execution-specs",
                "commit": "9edc7d5ad795e9708ac985839e9c92de8fc30dee",
                "committed_at": "2025-10-16T13:55:11-04:00",
                "immutable_url": "https://github.com/ethereum/execution-specs/commit/9edc7d5ad795e9708ac985839e9c92de8fc30dee",
            },
            {
                "event": "EEST tests moved from tests/eest to the EELS top-level tests directory",
                "repository": "ethereum/execution-specs",
                "commit": "2648ffcda8d32cf38c22943d50e325edcb34e504",
                "committed_at": "2025-10-21T16:50:11+01:00",
                "immutable_url": "https://github.com/ethereum/execution-specs/commit/2648ffcda8d32cf38c22943d50e325edcb34e504",
            },
            {
                "event": "EEST default branch records weld finalization and disables CI workflows",
                "repository": "ethereum/execution-spec-tests",
                "commit": "e9958ed222364f27c4171128263c3ff5df7eb38d",
                "committed_at": "2025-11-06T12:03:05+00:00",
                "effective_at": "2025-11-01",
                "immutable_url": "https://github.com/ethereum/execution-spec-tests/commit/e9958ed222364f27c4171128263c3ff5df7eb38d",
            },
            {
                "event": "EEST README changed to fully archived status",
                "repository": "ethereum/execution-spec-tests",
                "commit": "10eaa63d5da2f50b63d4359968f36542212f9f50",
                "committed_at": "2026-07-02T13:20:49+02:00",
                "immutable_url": "https://github.com/ethereum/execution-spec-tests/commit/10eaa63d5da2f50b63d4359968f36542212f9f50",
            },
        ],
        "path_and_generation_boundaries": [
            "The original EEST Python files are source tests that generate JSON fixtures through a transition tool; generated release fixtures are not treated as repository-snapshot evidence.",
            "EEST first appeared in EELS as a submodule, then under tests/eest as a subtree, then under top-level tests and testing packages. Historical lookup uses the path in each resolved tree.",
            "No external fixture release, Hive checkout, client implementation, or current generated output was used in a maturity judgment.",
        ],
        "unknowns": [
            "Local Git establishes commit and tree chronology but does not independently preserve GitHub repository-archive metadata or web publication timestamps beyond the upstream default-branch history.",
        ],
    }


def make_repository_judgment(
    fork: str,
    number: int,
    repository_id: str,
    cutoff: str,
) -> dict[str, Any]:
    repository = REPOSITORIES[repository_id]
    repo = repository["path"]
    command = (
        f"git -C {repo} rev-list --first-parent -1 "
        f"--before={cutoff} {repository['base_ref']}"
    )
    snapshot = git(
        repo,
        "rev-list",
        "--first-parent",
        "-1",
        f"--before={cutoff}",
        repository["base_ref"],
    )
    committed_at = git(repo, "show", "-s", "--format=%cI", snapshot)
    tree_sha = git(repo, "rev-parse", f"{snapshot}^{{tree}}")
    search = exact_search(repo, snapshot, number)
    decision = EVIDENCE.get((fork, number, repository_id))
    if decision is None:
        maturity = "absent"
        method_use = "exclude"
        gain = "none"
        rationale = (
            "No EIP-specific specification module, test source, fixture source, configuration, scaffold, TODO, skip, or behavior was found in the cutoff snapshot."
        )
        gain_summary = "The repository adds no information beyond the historical EIP text at this cutoff."
        risks = ["Using later repository content would cross the information cutoff."]
        confidence = "medium"
        unknowns = [
            "A pre-number working name or unnumbered branch that left no trace in the default-branch snapshot cannot be ruled out."
        ]
        paths: list[str] = []
    else:
        maturity = decision["maturity"]
        method_use = decision["use"]
        gain = decision["gain"]
        rationale = decision["rationale"]
        gain_summary = decision["gain_summary"]
        risks = decision["risks"]
        confidence = decision["confidence"]
        unknowns = decision["unknowns"]
        paths = decision["paths"]
    blobs = [blob_record(repository, snapshot, path, relevance(path)) for path in paths]
    if maturity not in MATURITY or method_use not in METHOD_USE:
        raise RuntimeError(f"invalid decision enum for {fork}/EIP-{number}/{repository_id}")
    rejected_hits = []
    if (fork, number, repository_id) == ("amsterdam", 7954, "execution_specs"):
        rejected_hits.append(
            {
                "kind": "commit_subject",
                "value": "chore(tests|forks): add max blobs per tx limit in eip4844 & eip7954 (#1884)",
                "reason": "The changed paths and content concern blob-count limits and EIP-7594-era tests, not EIP-7954 Increase Maximum Contract Size; the subject's transposed number is a false positive.",
            }
        )
    negative_note = (
        "No relevant material remained after exact-number path, content, and commit-subject searches plus review of fork-specific candidates."
        if not blobs
        else "All retained positive paths are listed as exact historical blobs; other search hits were references, empty package markers, generic framework files, or semantically unrelated matches."
    )
    return {
        "repository": repository["name"],
        "snapshot": {
            "base_ref": repository["base_ref"],
            "resolution_command": command,
            "commit": snapshot,
            "committed_at": committed_at,
            "tree_sha": tree_sha,
            "at_or_before_cutoff": parse_instant(committed_at) <= parse_instant(cutoff),
        },
        "search": {
            **search,
            "post_cutoff_navigation_used": False,
            "rejected_hits": rejected_hits,
            "negative_search_note": negative_note,
        },
        "publicly_present_by_cutoff": bool(blobs),
        "relevant_blobs": blobs,
        "maturity": maturity,
        "maturity_rationale": rationale,
        "methodological_use": method_use,
        "methodological_use_rationale": (
            "No assessor exposure is justified."
            if method_use == "exclude"
            else (
                "Retain for historical provenance, but do not expose it to an assessor or use it to change criterion scores."
                if method_use == "provenance_only"
                else (
                    "Allow only in a separately approved sensitivity run using the exact blobs and hashes listed here."
                    if method_use == "supplementary_candidate"
                    else "Use only under the separately defined methodological class."
                )
            )
        ),
        "information_gain": {"level": gain, "summary": gain_summary},
        "reference_spec_binding": (
            decision.get("reference_spec_binding") if decision else None
        ),
        "hindsight_or_construct_risks": risks,
        "confidence": {
            "level": confidence,
            "rationale": (
                "The clone is complete and exact-number searches cover the full snapshot, but an unnumbered or pre-number artifact cannot be ruled out."
                if maturity == "absent"
                else "The local clone is complete and the judgment is tied to an exact default-branch snapshot and blobs."
            ),
        },
        "unknowns": unknowns,
        "provenance": {
            "repository_path": str(repo),
            "remote": repository["github"],
            "timestamp_basis": "committer time",
            "inspection_boundary": f"tree and blobs at {snapshot}",
        },
    }


def collect() -> None:
    dump_yaml(TASK_ROOT / "outputs/repositories.yaml", repository_record())
    fork_counts: dict[str, Counter[tuple[str, str]]] = {fork: Counter() for fork in FORKS}
    fork_inventory: dict[str, list[int]] = {fork: [] for fork in FORKS}
    for fork in FORKS:
        for task04_path in sorted((TASK04_ROOT / fork).glob("eip-*.yaml")):
            task04 = load_yaml(task04_path)
            if task04["review"]["status"] != "approved":
                continue
            number = int(task04["eip"]["number"])
            if "execution" not in task04["eip"]["layers"]:
                continue
            raw_cutoff = str(task04["selection"]["information_cutoff_at"])
            cutoff = normalized_cutoff(raw_cutoff)
            judgments = {
                repository_id: make_repository_judgment(
                    fork, number, repository_id, cutoff
                )
                for repository_id in REPOSITORIES
            }
            for judgment in judgments.values():
                fork_counts[fork][("maturity", judgment["maturity"])] += 1
                fork_counts[fork][
                    ("methodological_use", judgment["methodological_use"])
                ] += 1
            available = [
                value
                for value in judgments.values()
                if value["methodological_use"] not in {"exclude", "provenance_only"}
            ]
            recommended = (
                "supplementary_candidate"
                if any(
                    value["methodological_use"] == "supplementary_candidate"
                    for value in judgments.values()
                )
                else "exclude"
            )
            relative_task04 = task04_path.relative_to(REPO_ROOT).as_posix()
            selected = task04["selection"]["selected_revision"]
            output = {
                "schema_version": 1,
                "task_id": TASK_ID,
                "fork_id": fork,
                "eip": {
                    "number": number,
                    "title": task04["eip"]["title"],
                    "layers": task04["eip"]["layers"],
                },
                "inputs": {
                    "task04_record": relative_task04,
                    "task04_review_status": "approved",
                    "information_cutoff_at": raw_cutoff,
                    "normalized_information_cutoff_at": cutoff,
                    "selected_eip_revision": {
                        "commit": selected["commit"],
                        "git_blob_sha": selected["git_blob_sha"],
                        "content_sha256": selected["content_sha256"],
                    },
                },
                "repositories": judgments,
                "overall": {
                    "artifact_assistance_available": bool(available),
                    "recommended_use": recommended,
                    "rationale": (
                        "At least one contemporaneous, exact-blob source is suitable only for a separately approved sensitivity run."
                        if available
                        else "No candidate repository source is safe and useful enough to expose in the primary proposal-time assessment."
                    ),
                },
            }
            dump_yaml(
                TASK_ROOT / f"outputs/fork-eips/{fork}/eip-{number}.yaml",
                output,
            )
            fork_inventory[fork].append(number)
    for fork in FORKS:
        maturity = {
            value: fork_counts[fork][("maturity", value)]
            for value in sorted(MATURITY)
        }
        method_use = {
            value: fork_counts[fork][("methodological_use", value)]
            for value in sorted(METHOD_USE)
        }
        dump_yaml(
            TASK_ROOT / f"outputs/forks/{fork}.yaml",
            {
                "schema_version": 1,
                "task_id": TASK_ID,
                "fork_id": fork,
                "eip_count": len(fork_inventory[fork]),
                "repository_eip_judgment_count": len(fork_inventory[fork])
                * len(REPOSITORIES),
                "eips": sorted(fork_inventory[fork]),
                "counts": {
                    "maturity": maturity,
                    "methodological_use": method_use,
                },
                "primary_candidate_count": method_use["primary_candidate"],
                "supplementary_candidate_count": method_use[
                    "supplementary_candidate"
                ],
            },
        )


if __name__ == "__main__":
    collect()
