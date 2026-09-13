#!/usr/bin/env python3
"""Capture and parse STEEL human complexity checklists for the Hegotá candidate population.

Two subcommands keep network access separate from deterministic parsing:

    capture   Query GitHub through the ``gh`` CLI for the ``ethspecs/pm`` default branch and every open
              pull request touching ``complexity_assessments/EIPs``.  Raw checklist bodies are archived under
              ``raw/<snapshot-id>/`` (the upstream repository is CC0-1.0) together with a capture manifest.
    parse     Read only the archived raw bodies and the capture manifest, parse every checklist, derive the
              per-EIP human-assessment status, and write the frozen ``outputs/`` records.

The population is the 46-entry Task 08 Hegotá candidate snapshot.  This task never scores anything: a
blank checklist cell is only interpreted as zero when the published total proves the arithmetic.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
RAW_ROOT = TASK_ROOT / "raw"
OUTPUT_ROOT = TASK_ROOT / "outputs"
POPULATION_PATH = (
    REPO_ROOT
    / "research/tasks/08-hegota-prospective-complexity-assessment/outputs/summary-all-candidates.yaml"
)
UPSTREAM = "ethspecs/pm"
ASSESSMENT_DIR = "complexity_assessments/EIPs"
TASK_ID = "09-hegota-human-assessment-snapshot"

# Criterion identifiers are shared with Task 05 / Task 08 (revision 2) and Task 05c (revision 1).
REVISION_1_ORDER = [
    ("evm_gas_rule_changes", "EVM Gas rule changes"),
    ("blob_gas_accounting_changes", "Blob gas accounting changes"),
    ("new_evm_gas_refund", "New EVM gas refund"),
    ("patterns_affecting_pre_existing_tests", "Patterns affecting pre-existing tests"),
    ("transition_tool_interface_changes", "Transition-tool interface changes"),
    ("cryptography", "Cryptography-related testing"),
    ("edge_boundary_conditions", "Edge/boundary conditions"),
    ("block_syncing_changes", "Block syncing changes"),
    ("engine_api_changes", "Engine API changes"),
    ("engine_api_encoding_changes", "Engine API encoding changes"),
    ("added_system_contracts", "Added system contracts"),
    ("modified_system_contracts", "Modified system contracts"),
    ("added_opcodes", "Added opcodes"),
    ("modified_opcodes", "Modified opcodes"),
    ("added_precompiles", "Added precompiles"),
    ("modified_precompiles", "Modified precompiles"),
    ("encoding_changes_rlp_ssz", "Encoding changes (RLP/SSZ)"),
    ("new_transaction_types", "New transaction types"),
    ("new_or_modified_transaction_validity_mechanisms", "New or modified transaction validity mechanisms"),
    ("new_block_header_fields", "New block / header fields"),
    ("new_fork_activation_mechanism", "New fork activation mechanism"),
    ("performance_risks", "Performance risks"),
    ("security_risks", "Security risks"),
    ("cross_eip_interactions", "Cross-EIP interactions"),
]
REVISION_2_ORDER = [
    ("evm_gas_rule_changes", "EVM Gas rule changes"),
    ("state_access_ordering_within_opcode_execution", "State-access ordering within opcode execution"),
    ("blob_gas_accounting_changes", "Blob gas accounting changes"),
    ("state_gas_accounting_changes", "State gas accounting changes"),
    ("new_evm_gas_refund", "New EVM gas refund"),
    ("patterns_affecting_pre_existing_tests", "Patterns affecting pre-existing tests"),
    ("new_invariant_on_pre_existing_tests", "New invariant on pre-existing tests"),
    ("transition_tool_interface_changes", "Transition-tool interface changes"),
    ("new_test_framework_primitives", "New test-framework primitives"),
    ("cryptography", "Cryptography"),
    ("edge_boundary_conditions", "Edge/boundary conditions"),
    ("block_syncing_changes", "Block syncing changes"),
    ("engine_api_changes", "Engine API changes"),
    ("added_system_contracts", "Added system contracts"),
    ("modified_system_contracts", "Modified system contracts"),
    ("added_opcodes", "Added opcodes"),
    ("modified_opcodes", "Modified opcodes"),
    ("added_precompiles", "Added precompiles"),
    ("modified_precompiles", "Modified precompiles"),
    ("encoding_changes_rlp_ssz", "Encoding changes (RLP/SSZ)"),
    ("new_transaction_types", "New transaction types"),
    ("new_or_modified_transaction_validity_mechanisms", "New or modified transaction validity mechanisms"),
    ("new_block_header_fields", "New block / header fields"),
    ("new_fork_activation_mechanism", "New fork activation mechanism"),
    ("performance_risks", "Performance risks"),
    ("security_risks", "Security risks"),
    ("unspecified_behavior_requiring_cross_client_consensus", "Unspecified behavior requiring cross-client consensus"),
    ("cross_eip_interactions", "Cross-EIP interactions"),
]
LABEL_ALIASES = {
    "cryptography-related testing": "cryptography",
    "cryptography": "cryptography",
}
RUBRICS = {
    1: {
        "order": [item[0] for item in REVISION_1_ORDER],
        "nominal_maximum": 72,
        "tier_thresholds": {"low": {"minimum": 0, "maximum": 9}, "medium": {"minimum": 10, "maximum": 19}, "high": {"minimum": 20, "maximum": None}},
    },
    2: {
        "order": [item[0] for item in REVISION_2_ORDER],
        "nominal_maximum": 84,
        "tier_thresholds": {"low": {"minimum": 0, "maximum": 11}, "medium": {"minimum": 12, "maximum": 22}, "high": {"minimum": 23, "maximum": None}},
    },
}
CRITERION_BY_LABEL: dict[str, str] = {}
for _identifier, _label in [*REVISION_1_ORDER, *REVISION_2_ORDER]:
    CRITERION_BY_LABEL[_label.lower()] = _identifier
CRITERION_BY_LABEL.update(LABEL_ALIASES)

STATUS_ORDER = ["complete", "available_in_open_pr", "in_progress", "incomplete", "not_yet_available"]


class SnapshotError(RuntimeError):
    """Raised when a source or archived artifact violates the task contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def gh_api(endpoint: str, *, paginate: bool = False) -> Any:
    command = ["gh", "api", "-H", "Accept: application/vnd.github+json"]
    if paginate:
        command.append("--paginate")
    command.append(endpoint)
    result = subprocess.run(command, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise SnapshotError(f"gh api {endpoint} failed: {result.stderr.decode(errors='replace').strip()}")
    text = result.stdout.decode()
    if not paginate:
        return json.loads(text)
    # ``--paginate`` concatenates one JSON array per page; decode them in sequence.
    decoder = json.JSONDecoder()
    merged: list[Any] = []
    index = 0
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        page, offset = decoder.raw_decode(text, index)
        merged.extend(page)
        index = offset
    return merged


def yaml_dump(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SnapshotError(f"expected mapping: {path}")
    return data


def population() -> tuple[dict[int, dict[str, Any]], dict[str, str]]:
    summary = load_yaml(POPULATION_PATH)
    entries: dict[int, dict[str, Any]] = {}
    for row in summary["scored_eips"]:
        entries[row["eip"]] = {"eip": row["eip"], "title": row["title"], "snapshot_status": row["snapshot_status"], "llm_disposition": "scored"}
    for row in summary["not_applicable_eips"]:
        entries[row["eip"]] = {"eip": row["eip"], "title": row["title"], "snapshot_status": row["snapshot_status"], "llm_disposition": "not_applicable"}
    source = {
        "path": POPULATION_PATH.relative_to(REPO_ROOT).as_posix(),
        "sha256": sha256_bytes(POPULATION_PATH.read_bytes()),
        "snapshot_id": summary["snapshot"]["snapshot_id"],
    }
    return entries, source


def eip_number(path: str) -> int | None:
    match = re.fullmatch(rf"{re.escape(ASSESSMENT_DIR)}/EIP-(\d+)\.md", path)
    return int(match.group(1)) if match else None


def fetch_content(path: str, ref: str) -> tuple[bytes, str]:
    payload = gh_api(f"repos/{UPSTREAM}/contents/{path}?ref={ref}")
    if payload.get("encoding") != "base64":
        raise SnapshotError(f"unexpected content encoding for {path}@{ref}")
    return base64.b64decode(payload["content"]), payload["sha"]


# ---------------------------------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------------------------------


def capture(args: argparse.Namespace) -> int:
    entries, population_source = population()
    captured_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    repository = gh_api(f"repos/{UPSTREAM}")
    default_branch = repository["default_branch"]
    head = gh_api(f"repos/{UPSTREAM}/commits/{default_branch}")
    head_sha = head["sha"]
    snapshot_id = f"hegota-human-{captured_at[:10]}-{head_sha[:7]}"
    raw_root = RAW_ROOT / snapshot_id
    if raw_root.exists() and not args.force:
        raise SnapshotError(f"raw snapshot already exists: {raw_root.relative_to(REPO_ROOT)} (use --force)")

    main_files: list[dict[str, Any]] = []
    listing = gh_api(f"repos/{UPSTREAM}/contents/{ASSESSMENT_DIR}?ref={head_sha}")
    for item in sorted(listing, key=lambda value: value["path"]):
        number = eip_number(item["path"])
        if number is None or number not in entries:
            continue
        body, blob = fetch_content(item["path"], head_sha)
        commits = gh_api(f"repos/{UPSTREAM}/commits?path={item['path']}&sha={head_sha}&per_page=1")
        last_commit = commits[0]
        archive = raw_root / "main" / f"EIP-{number}.md"
        write_text(archive, body.decode("utf-8"))
        main_files.append(
            {
                "eip": number,
                "path": item["path"],
                "git_blob_sha": blob,
                "content_sha256": sha256_bytes(body),
                "last_commit": last_commit["sha"],
                "last_committed_at": last_commit["commit"]["committer"]["date"],
                "immutable_url": f"https://github.com/{UPSTREAM}/blob/{head_sha}/{item['path']}",
                "archive_path": archive.relative_to(REPO_ROOT).as_posix(),
            }
        )

    pull_requests: list[dict[str, Any]] = []
    for pull in gh_api(f"repos/{UPSTREAM}/pulls?state=open&per_page=100", paginate=True):
        files = gh_api(f"repos/{UPSTREAM}/pulls/{pull['number']}/files?per_page=100", paginate=True)
        matched: list[dict[str, Any]] = []
        for file_item in sorted(files, key=lambda value: value["filename"]):
            number = eip_number(file_item["filename"])
            if number is None or number not in entries or file_item["status"] == "removed":
                continue
            body, blob = fetch_content(file_item["filename"], pull["head"]["sha"])
            archive = raw_root / f"pr-{pull['number']}" / f"EIP-{number}.md"
            write_text(archive, body.decode("utf-8"))
            matched.append(
                {
                    "eip": number,
                    "path": file_item["filename"],
                    "change_status": file_item["status"],
                    "git_blob_sha": blob,
                    "content_sha256": sha256_bytes(body),
                    "immutable_url": f"https://github.com/{UPSTREAM}/blob/{pull['head']['sha']}/{file_item['filename']}",
                    "archive_path": archive.relative_to(REPO_ROOT).as_posix(),
                }
            )
        if not matched:
            continue
        pull_requests.append(
            {
                "number": pull["number"],
                "title": pull["title"],
                "url": pull["html_url"],
                "draft": bool(pull["draft"]),
                "head_sha": pull["head"]["sha"],
                "head_ref": pull["head"]["ref"],
                "head_repository": (pull["head"]["repo"] or {}).get("full_name"),
                "created_at": pull["created_at"],
                "updated_at": pull["updated_at"],
                "files": matched,
            }
        )
    pull_requests.sort(key=lambda value: value["number"])

    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "snapshot_id": snapshot_id,
        "captured_at": captured_at,
        "capture_method": "gh api (GitHub REST); raw checklist bodies archived verbatim under raw/",
        "upstream": {
            "repository": UPSTREAM,
            "license": repository.get("license", {}).get("spdx_id"),
            "default_branch": default_branch,
            "head_commit": head_sha,
            "head_committed_at": head["commit"]["committer"]["date"],
            "assessment_directory": ASSESSMENT_DIR,
        },
        "population": {"source": population_source, "count": len(entries)},
        "default_branch_files": main_files,
        "open_pull_requests": pull_requests,
    }
    write_text(raw_root / "capture-manifest.yaml", yaml_dump(manifest))
    print(json.dumps({"snapshot_id": snapshot_id, "default_branch_files": len(main_files), "pull_requests": len(pull_requests)}))
    return 0


# ---------------------------------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------------------------------


def normalize_label(value: str) -> str:
    cleaned = value.replace("**", "")
    cleaned = re.sub(r"\((?:uncapped)\)", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_additive_score(raw: str) -> tuple[list[int] | None, int | None]:
    value = raw.strip()
    if not value:
        return None, None
    if not re.fullmatch(r"\d+(?:\s*\+\s*\d+)*", value):
        return None, None
    terms = [int(item.strip()) for item in value.split("+")]
    return terms, sum(terms)


def tier_for(total: int, revision: int) -> str:
    thresholds = RUBRICS[revision]["tier_thresholds"]
    for name in ("low", "medium", "high"):
        limits = thresholds[name]
        if total >= limits["minimum"] and (limits["maximum"] is None or total <= limits["maximum"]):
            return name
    raise SnapshotError(f"total {total} matches no tier")


def parse_checklist(text: str) -> dict[str, Any]:
    """Parse one STEEL checklist body into structured, unscored-by-us data."""
    notes: list[str] = []
    revision_match = re.search(r"Checklist revision:\s*\*\*(\d+)\*\*", text)
    declared_revision = int(revision_match.group(1)) if revision_match else None
    marker = re.search(r"^### Checklist\s*$", text, re.MULTILINE)
    if marker is None:
        return {"parse_state": "no_checklist", "parser_notes": ["No '### Checklist' section found."]}
    end = text.find("\n**Total:", marker.end())
    total_line_present = end >= 0
    if not total_line_present:
        end = len(text)
        notes.append("No '**Total:**' line follows the checklist table.")
    rows: list[dict[str, Any]] = []
    unknown_rows: list[str] = []
    for line in text[marker.end() : end].splitlines():
        match = re.match(r"^\|\s*\*\*(.+?)\*\*(.*?)\|\s*(.*?)\s*\|\s*(.*?)\s*\|?\s*$", line)
        if match is None:
            continue
        label = normalize_label(match.group(1) + match.group(2))
        criterion_id = CRITERION_BY_LABEL.get(label.lower())
        if criterion_id is None:
            unknown_rows.append(label)
            continue
        raw_score = match.group(3)
        terms, contribution = parse_additive_score(raw_score)
        rows.append(
            {
                "id": criterion_id,
                "label": label,
                "raw_score_cell": raw_score,
                "parsed_terms": terms,
                "numeric_contribution": contribution,
                "rationale": match.group(4).strip(),
                "blank_interpretation": None,
            }
        )
    if unknown_rows:
        notes.append("Unrecognized checklist rows were ignored: " + ", ".join(unknown_rows))
    order = [row["id"] for row in rows]
    revision: int | None = None
    for candidate, rubric in RUBRICS.items():
        if order == rubric["order"]:
            revision = candidate
    if revision is None:
        notes.append("Checklist row inventory matches neither revision 1 nor revision 2 exactly.")
        revision = declared_revision if declared_revision in RUBRICS else (2 if len(order) > 24 else 1)
    elif declared_revision is not None and declared_revision != revision:
        notes.append(f"Declared checklist revision {declared_revision} disagrees with the row inventory (revision {revision}).")

    published_total = None
    total_match = re.search(r"^\*\*Total:\s*(\d+)\*\*", text, re.MULTILINE)
    if total_match:
        published_total = int(total_match.group(1))
    final_match = re.search(r"\|\s*\*\*Total Score\*\*\s*\|.*?\|\s*\**`?(\d+)`?\**\s*\|", text)
    final_total = int(final_match.group(1)) if final_match else None
    if published_total is None:
        published_total = final_total
    elif final_total is not None and final_total != published_total:
        notes.append("The checklist total and the Final Assessment total differ.")
    tier_match = re.search(r"\|\s*\*\*Complexity Tier\*\*\s*\|.*?\|\s*([^|]+?)\s*\|", text)
    raw_tier = tier_match.group(1).strip() if tier_match else None
    published_tier = None
    for symbol, name in (("🟢", "low"), ("🟡", "medium"), ("🔴", "high")):
        if raw_tier and symbol in raw_tier:
            published_tier = name
    if raw_tier and "/" in raw_tier and published_tier:
        published_tier = None
        notes.append("The Final Assessment tier cell still lists every tier symbol.")

    known_sum = sum(row["numeric_contribution"] or 0 for row in rows)
    blanks = [row for row in rows if row["numeric_contribution"] is None and not row["raw_score_cell"].strip()]
    invalid = [row for row in rows if row["numeric_contribution"] is None and row["raw_score_cell"].strip()]
    if invalid:
        notes.append("Nonblank score cells that are not additive integers: " + ", ".join(row["label"] for row in invalid))
    if blanks:
        if published_total is not None and published_total == known_sum:
            for row in blanks:
                row["numeric_contribution"] = 0
                row["parsed_terms"] = []
                row["blank_interpretation"] = "explicit_zero_by_published_arithmetic"
            notes.append(
                f"{len(blanks)} blank score cells are interpreted as zero only because the published total equals the sum of every nonblank cell."
            )
        else:
            notes.append(f"{len(blanks)} blank score cells remain unresolved because the published total does not establish zero.")
    numeric_complete = bool(rows) and not invalid and all(row["numeric_contribution"] is not None for row in rows)
    recomputed_total = sum(row["numeric_contribution"] for row in rows) if numeric_complete else None
    recomputed_tier = tier_for(recomputed_total, revision) if recomputed_total is not None else None
    if published_total is not None and recomputed_total is not None and published_total != recomputed_total:
        notes.append("Published and recomputed totals differ.")
    missing_rows = [identifier for identifier in RUBRICS[revision]["order"] if identifier not in order]
    if missing_rows:
        notes.append("Checklist rows missing for this revision: " + ", ".join(missing_rows))
    complete = (
        numeric_complete
        and not missing_rows
        and published_total is not None
        and published_total == recomputed_total
    )
    return {
        "parse_state": "complete" if complete else "incomplete",
        "rubric_revision": revision,
        "declared_revision": declared_revision,
        "scores": rows,
        "published_total": published_total,
        "published_tier_raw": raw_tier,
        "published_tier": published_tier,
        "recomputed_total": recomputed_total,
        "recomputed_tier": recomputed_tier,
        "unresolved_blank_rows": [row["id"] for row in blanks if row["numeric_contribution"] is None],
        "invalid_score_rows": [row["id"] for row in invalid],
        "missing_rows": missing_rows,
        "parser_notes": notes,
    }


def score_fingerprint(parsed: dict[str, Any]) -> str:
    """Identify a checklist by its score cells and published total, ignoring rationale wording."""
    if "scores" not in parsed:
        return "unparsed"
    payload = [(row["id"], row["raw_score_cell"].strip()) for row in parsed["scores"]]
    return sha256_bytes(json.dumps([payload, parsed["published_total"]], sort_keys=True).encode())


def status_for(candidates: list[dict[str, Any]]) -> tuple[str, str | None]:
    """Return (status, preferred candidate id) using the smallest status set the sources support."""
    if not candidates:
        return "not_yet_available", None

    def rank(candidate: dict[str, Any]) -> tuple[int, int, int, str]:
        complete = 0 if candidate["parse_state"] == "complete" else 1
        availability = {"merged": 0, "open_pull_request": 1, "open_draft_pull_request": 2}[candidate["availability"]]
        revision = -(candidate.get("rubric_revision") or 0)
        return (complete, revision, availability, candidate["candidate_id"])

    preferred = sorted(candidates, key=rank)[0]
    if preferred["parse_state"] != "complete":
        status = "in_progress" if preferred["availability"] == "open_draft_pull_request" else "incomplete"
    elif preferred["availability"] == "merged":
        status = "complete"
    elif preferred["availability"] == "open_pull_request":
        status = "available_in_open_pr"
    else:
        status = "in_progress"
    return status, preferred["candidate_id"]


def parse(args: argparse.Namespace) -> int:
    raw_root = RAW_ROOT / args.snapshot_id
    manifest = load_yaml(raw_root / "capture-manifest.yaml")
    entries, population_source = population()
    if manifest["population"]["source"]["sha256"] != population_source["sha256"]:
        raise SnapshotError("Task 08 population changed since capture")
    per_eip: dict[int, list[dict[str, Any]]] = {number: [] for number in entries}

    def archived_text(record: dict[str, Any]) -> str:
        path = REPO_ROOT / record["archive_path"]
        body = path.read_bytes()
        if sha256_bytes(body) != record["content_sha256"]:
            raise SnapshotError(f"archived body hash mismatch: {record['archive_path']}")
        return body.decode("utf-8")

    for record in manifest["default_branch_files"]:
        parsed = parse_checklist(archived_text(record))
        per_eip[record["eip"]].append(
            {
                "candidate_id": f"main@{manifest['upstream']['head_commit'][:12]}",
                "availability": "merged",
                "source": {
                    "kind": "default_branch",
                    "repository": UPSTREAM,
                    "branch": manifest["upstream"]["default_branch"],
                    "commit": manifest["upstream"]["head_commit"],
                    "last_commit": record["last_commit"],
                    "last_committed_at": record["last_committed_at"],
                    "path": record["path"],
                    "git_blob_sha": record["git_blob_sha"],
                    "content_sha256": record["content_sha256"],
                    "immutable_url": record["immutable_url"],
                    "archive_path": record["archive_path"],
                },
                **parsed,
            }
        )
    for pull in manifest["open_pull_requests"]:
        for record in pull["files"]:
            parsed = parse_checklist(archived_text(record))
            per_eip[record["eip"]].append(
                {
                    "candidate_id": f"pr-{pull['number']}@{pull['head_sha'][:12]}",
                    "availability": "open_draft_pull_request" if pull["draft"] else "open_pull_request",
                    "source": {
                        "kind": "open_pull_request",
                        "repository": UPSTREAM,
                        "pull_request": pull["number"],
                        "pull_request_title": pull["title"],
                        "pull_request_url": pull["url"],
                        "draft": pull["draft"],
                        "head_sha": pull["head_sha"],
                        "created_at": pull["created_at"],
                        "updated_at": pull["updated_at"],
                        "path": record["path"],
                        "git_blob_sha": record["git_blob_sha"],
                        "content_sha256": record["content_sha256"],
                        "immutable_url": record["immutable_url"],
                        "archive_path": record["archive_path"],
                    },
                    **parsed,
                }
            )

    assessments_root = OUTPUT_ROOT / "assessments"
    if assessments_root.exists():
        for stale in assessments_root.glob("eip-*.yaml"):
            stale.unlink()
    status_rows: list[dict[str, Any]] = []
    status_counts = {status: 0 for status in STATUS_ORDER}
    for number in sorted(entries):
        candidates = per_eip[number]
        merged_fingerprints = {score_fingerprint(candidate) for candidate in candidates if candidate["availability"] == "merged"}
        for candidate in candidates:
            candidate["duplicates_merged_scores"] = (
                candidate["availability"] != "merged" and score_fingerprint(candidate) in merged_fingerprints
            )
        distinct = [candidate for candidate in candidates if not candidate["duplicates_merged_scores"]]
        status, preferred = status_for(distinct)
        status_counts[status] += 1
        entry = entries[number]
        row = {
            "eip": number,
            "title": entry["title"],
            "snapshot_status": entry["snapshot_status"],
            "llm_disposition": entry["llm_disposition"],
            "human_assessment_status": status,
            "preferred_candidate": preferred,
            "candidate_count": len(distinct),
        }
        status_rows.append(row)
        if candidates:
            record = {
                "schema_version": 1,
                "task_id": TASK_ID,
                "snapshot_id": args.snapshot_id,
                "fork_id": "hegota",
                "eip": {"number": number, "title": entry["title"]},
                "human_assessment_status": status,
                "preferred_candidate": preferred,
                "candidates": candidates,
            }
            write_text(assessments_root / f"eip-{number}.yaml", yaml_dump(record))

    snapshot = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "snapshot_id": args.snapshot_id,
        "captured_at": manifest["captured_at"],
        "upstream": manifest["upstream"],
        "population": manifest["population"],
        "status_vocabulary": {
            "complete": "A complete checklist is merged on the upstream default branch.",
            "available_in_open_pr": "A complete checklist exists only in an open, non-draft pull request.",
            "in_progress": "The most advanced checklist is in an open draft pull request.",
            "incomplete": "A checklist exists but has unresolved score cells, missing rows, or no published total.",
            "not_yet_available": "No checklist exists on the default branch or in any open pull request.",
        },
        "status_counts": status_counts,
        "open_pull_requests": [
            {key: value for key, value in pull.items() if key != "files"} | {"eips": sorted(file_item["eip"] for file_item in pull["files"])}
            for pull in manifest["open_pull_requests"]
        ],
        "entries": status_rows,
    }
    write_text(OUTPUT_ROOT / "snapshot.yaml", yaml_dump(snapshot))
    print(json.dumps({"snapshot_id": args.snapshot_id, **status_counts}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture_parser = subparsers.add_parser("capture", help="Archive upstream checklist bodies (requires network and gh).")
    capture_parser.add_argument("--force", action="store_true", help="Overwrite an existing raw snapshot with the same identifier.")
    capture_parser.set_defaults(func=capture)
    parse_parser = subparsers.add_parser("parse", help="Parse an archived snapshot into frozen outputs (offline).")
    parse_parser.add_argument("--snapshot-id", required=True)
    parse_parser.set_defaults(func=parse)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SnapshotError as error:
        raise SystemExit(f"snapshot error: {error}") from error
