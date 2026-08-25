#!/usr/bin/env python3
"""Shared deterministic helpers for the Task 05c study."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import yaml


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK04_ROOT = REPO_ROOT / "research/tasks/04-complexity-assessment-ref-selection"
TASK05_ROOT = REPO_ROOT / "research/tasks/05-retrospective-complexity-assignment"
PM_REPO = REPO_ROOT.parent / "pm"
EIPS_REPO = REPO_ROOT.parent / "EIPs"
SOURCE_STATE = TASK_ROOT / "inputs/source-state.yaml"

APPROVED_ROOT = TASK04_ROOT / "outputs/fork-eips/amsterdam"
TASK05_PACKAGE_ROOT = TASK05_ROOT / "inputs/fork-eips/amsterdam"
TASK05_OUTPUT_ROOT = TASK05_ROOT / "outputs/fork-eips/amsterdam"
INVENTORY_PATH = TASK_ROOT / "inputs/study-inventory.yaml"
HUMAN_ROOT = TASK_ROOT / "inputs/human"
RUBRIC_ROOT = TASK_ROOT / "inputs/rubrics"
PACKAGE_ROOT = TASK_ROOT / "inputs/packages"
AUTOMATED_ROOT = TASK_ROOT / "outputs/automated"
COMPARISON_ROOT = TASK_ROOT / "outputs/comparisons"
FREEZE_PATH = TASK_ROOT / "outputs/automated-freeze.yaml"
DATASET_MANIFEST_PATH = TASK_ROOT / "outputs/dataset-manifest.yaml"
SUMMARY_PATH = TASK_ROOT / "outputs/alignment-summary.md"
CONTRACT_PATH = TASK_ROOT / "prompts/ASSESSMENT-CONTRACT.md"
ASSESSOR_PROMPT_PATH = TASK_ROOT / "prompts/assessor.md"


CRITERIA: list[tuple[str, str]] = [
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
    (
        "new_or_modified_transaction_validity_mechanisms",
        "New or modified transaction validity mechanisms",
    ),
    ("new_block_header_fields", "New block / header fields"),
    ("new_fork_activation_mechanism", "New fork activation mechanism"),
    ("performance_risks", "Performance risks"),
    ("security_risks", "Security risks"),
    ("cross_eip_interactions", "Cross-EIP interactions"),
]
CRITERION_BY_LABEL = {label: criterion_id for criterion_id, label in CRITERIA}
HEADING_BY_LABEL = {**CRITERION_BY_LABEL, "Cryptography": "cryptography"}
CONFIDENCE = {"low", "medium", "high"}
MATERIAL_HUMAN_CLASSES = {
    "initial_substantive_scoring",
    "substantive_score_change",
    "substantive_rationale_change",
}
TIER_THRESHOLDS = {
    "low": {"minimum": 0, "maximum": 9},
    "medium": {"minimum": 10, "maximum": 19},
    "high": {"minimum": 20, "maximum": None},
}


class StudyError(RuntimeError):
    """Raised when a source or generated artifact violates the study contract."""


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise StudyError(f"Timestamp has no offset: {value}")
    return parsed.astimezone(UTC)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise StudyError(f"Expected YAML mapping: {path}")
    return data


def yaml_bytes(data: Any) -> bytes:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    ).encode()


def write_bytes(path: Path, payload: bytes, *, overwrite: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() == payload:
            return
        if not overwrite:
            raise StudyError(f"Refusing to overwrite existing canonical file: {path}")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(payload)
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def write_yaml(path: Path, data: Any, *, overwrite: bool = True) -> None:
    write_bytes(path, yaml_bytes(data), overwrite=overwrite)


def run_git(repo: Path, *args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        message = result.stderr.decode(errors="replace").strip()
        raise StudyError(f"git {' '.join(args)} failed in {repo}: {message}")
    return result.stdout


def git_text(repo: Path, *args: str) -> str:
    return run_git(repo, *args).decode(errors="replace")


def git_commit_time(repo: Path, commit: str) -> str:
    value = git_text(repo, "show", "-s", "--format=%cI", commit).strip()
    return parse_time(value).isoformat().replace("+00:00", "Z")


def git_blob(repo: Path, commit: str, path: str) -> tuple[bytes, str]:
    payload = run_git(repo, "show", f"{commit}:{path}")
    blob = git_text(repo, "rev-parse", f"{commit}:{path}").strip()
    return payload, blob


def git_path_exists(repo: Path, commit: str, path: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{commit}:{path}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def latest_path_commit_at(repo: Path, path: str, timestamp: str) -> str:
    candidates: list[tuple[datetime, str]] = []
    raw = git_text(repo, "log", "--all", "--format=%H%x09%cI", "--", path)
    cutoff = parse_time(timestamp)
    for line in raw.splitlines():
        if not line.strip():
            continue
        commit, committed_at = line.split("\t", 1)
        instant = parse_time(committed_at)
        if instant <= cutoff:
            candidates.append((instant, commit))
    if not candidates:
        raise StudyError(f"No {path} commit exists at or before {timestamp}")
    return max(candidates)[1]


def repo_identity(name: str) -> dict[str, Any]:
    source = load_yaml(SOURCE_STATE)["repositories"][name]
    repo = Path(source["path"])
    head = git_text(repo, "rev-parse", "HEAD").strip()
    if head != source["head"]:
        raise StudyError(
            f"{name} repository HEAD changed since the recorded start: {head} != {source['head']}"
        )
    return source


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def record_payload_hash(record: dict[str, Any]) -> str:
    clone = json.loads(json.dumps(record))
    generation = clone.get("generation")
    if isinstance(generation, dict):
        generation["record_payload_sha256"] = None
    return sha256_bytes(yaml_bytes(clone))


def tier(total: int) -> str:
    if total < 10:
        return "low"
    if total < 20:
        return "medium"
    return "high"


def tiers_in_range(minimum: int, maximum: int) -> list[str]:
    values: list[str] = []
    for name, limits in TIER_THRESHOLDS.items():
        upper = limits["maximum"]
        if maximum >= limits["minimum"] and (upper is None or minimum <= upper):
            values.append(name)
    return values


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("**", "").strip())


def rubric_semantics(text: str) -> dict[str, Any]:
    anchor_marker = re.search(r"^#### (?:Anchors|Criteria)\s*$", text, re.MULTILINE)
    checklist_marker = re.search(r"^### Checklist\s*$", text, re.MULTILINE)
    if anchor_marker is None or checklist_marker is None or anchor_marker.end() >= checklist_marker.start():
        raise StudyError("Historical rubric does not contain the expected anchor/checklist boundaries")
    definitions_text = text[anchor_marker.end() : checklist_marker.start()]
    headings = list(re.finditer(r"^##### (.+?)\s*$", definitions_text, re.MULTILINE))
    definitions: dict[str, dict[str, Any]] = {}
    for index, match in enumerate(headings):
        label = normalize_label(match.group(1))
        criterion_id = HEADING_BY_LABEL.get(label)
        if criterion_id is None:
            raise StudyError(f"Unknown historical anchor heading: {label}")
        end = headings[index + 1].start() if index + 1 < len(headings) else len(definitions_text)
        body = definitions_text[match.end() : end].strip()
        domain = sorted({int(value) for value in re.findall(r"^- (\d+)\.", body, re.MULTILINE)})
        definitions[criterion_id] = {
            "heading": label,
            "definition": body,
            "defined_scores": domain,
        }

    checklist_end = text.find("\n**Total:", checklist_marker.end())
    if checklist_end < 0:
        raise StudyError("Historical rubric checklist has no Total boundary")
    checklist_text = text[checklist_marker.end() : checklist_end]
    checklist: list[dict[str, Any]] = []
    for line in checklist_text.splitlines():
        match = re.match(r"^\|\s*\*\*(.+?)\*\*\s*\|", line)
        if match is None:
            continue
        label = normalize_label(match.group(1))
        criterion_id = CRITERION_BY_LABEL.get(label)
        if criterion_id is None:
            raise StudyError(f"Unknown historical checklist row: {label}")
        definition = definitions.get(criterion_id)
        defined_scores = definition["defined_scores"] if definition else []
        base_scores = defined_scores or [0, 1, 2, 3]
        checklist.append(
            {
                "id": criterion_id,
                "label": label,
                "definition_present": definition is not None,
                "definition": definition["definition"] if definition else None,
                "base_allowed_scores": base_scores,
                "allowed_scores": sorted(set([*base_scores, 4])),
            }
        )
    expected = [criterion_id for criterion_id, _ in CRITERIA]
    actual = [item["id"] for item in checklist]
    if actual != expected:
        raise StudyError(f"Historical checklist order differs: {actual}")
    return {
        "criteria": checklist,
        "nominal_maximum": 72,
        "exceptional_score": 4,
        "tier_thresholds": TIER_THRESHOLDS,
    }


def parse_additive_score(raw: str) -> tuple[list[int] | None, int | None]:
    value = raw.strip()
    if not value:
        return None, None
    if not re.fullmatch(r"\d+(?:\s*\+\s*\d+)*", value):
        return None, None
    terms = [int(item.strip()) for item in value.split("+")]
    return terms, sum(terms)


def extract_human_scores(text: str, semantics: dict[str, Any]) -> dict[str, Any]:
    marker = re.search(r"^### Checklist\s*$", text, re.MULTILINE)
    if marker is None:
        raise StudyError("Human assessment has no Checklist section")
    end = text.find("\n**Total:", marker.end())
    if end < 0:
        raise StudyError("Human assessment has no checklist Total line")
    rows: dict[str, dict[str, Any]] = {}
    for line in text[marker.end() : end].splitlines():
        match = re.match(
            r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*$",
            line,
        )
        if match is None:
            continue
        label = normalize_label(match.group(1))
        criterion_id = CRITERION_BY_LABEL.get(label)
        if criterion_id is None:
            continue
        raw_score = match.group(2)
        terms, contribution = parse_additive_score(raw_score)
        rows[criterion_id] = {
            "id": criterion_id,
            "label": label,
            "raw_score_cell": raw_score,
            "parsed_terms": terms,
            "numeric_contribution": contribution,
            "rationale": match.group(3).strip(),
            "blank_interpretation": None,
        }
    expected = [item["id"] for item in semantics["criteria"]]
    if list(rows) != expected:
        raise StudyError(f"Human checklist row inventory/order differs: {list(rows)}")

    final_match = re.search(
        r"\|\s*\*\*Total Score\*\*\s*\|.*?\|\s*\*\*?`?(\d+)`?\*\*?\s*\|",
        text,
    )
    if final_match is None:
        final_match = re.search(r"\|\s*\*\*Total Score\*\*\s*\|.*?\|\s*`?(\d+)`?\s*\|", text)
    published_total = int(final_match.group(1)) if final_match else None
    tier_match = re.search(r"\|\s*\*\*Complexity Tier\*\*\s*\|.*?\|\s*([^|]+?)\s*\|", text)
    raw_tier = tier_match.group(1).strip() if tier_match else None
    published_tier = None
    if raw_tier:
        for symbol, name in (("🟢", "low"), ("🟡", "medium"), ("🔴", "high")):
            if symbol in raw_tier:
                published_tier = name
                break

    known_sum = sum(item["numeric_contribution"] or 0 for item in rows.values())
    blanks = [item for item in rows.values() if item["numeric_contribution"] is None and not item["raw_score_cell"].strip()]
    invalid = [item for item in rows.values() if item["numeric_contribution"] is None and item["raw_score_cell"].strip()]
    notes: list[str] = []
    if invalid:
        notes.append("One or more nonblank score cells do not match the additive-integer grammar.")
    if blanks:
        if published_total is not None and published_total == known_sum:
            for item in blanks:
                item["numeric_contribution"] = 0
                item["parsed_terms"] = []
                item["blank_interpretation"] = "explicit_zero_by_published_arithmetic"
            notes.append(
                "Blank cells are interpreted as zero only because the published total exactly equals the sum of every nonblank parsed contribution."
            )
        else:
            notes.append("Blank score cells remain unresolved because published arithmetic does not establish zero.")
    numeric_complete = not invalid and all(item["numeric_contribution"] is not None for item in rows.values())
    recomputed_total = sum(item["numeric_contribution"] for item in rows.values()) if numeric_complete else None
    recomputed_tier = tier(recomputed_total) if recomputed_total is not None else None
    if published_total is not None and recomputed_total is not None and published_total != recomputed_total:
        notes.append("Published and recomputed totals differ.")
    return {
        "scores": list(rows.values()),
        "published_total": published_total,
        "published_tier_raw": raw_tier,
        "published_tier": published_tier,
        "recomputed_total": recomputed_total,
        "recomputed_tier": recomputed_tier,
        "numeric_total_unambiguous": (
            numeric_complete
            and published_total == recomputed_total
            and published_tier == recomputed_tier
        ),
        "parser_notes": notes,
    }


def human_score_fingerprint(text: str) -> dict[str, Any] | None:
    try:
        semantics = rubric_semantics(text)
        parsed = extract_human_scores(text, semantics)
    except StudyError:
        return None
    special_match = re.search(
        r"^#### Special Considerations\s*(.*?)(?=^#### Notes)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    notes_match = re.search(
        r"^#### Notes\s*(.*?)(?=^#### Final Assessment)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return {
        "rows": [
            {
                "id": item["id"],
                "raw": re.sub(r"\s+", " ", item["raw_score_cell"].strip()),
                "rationale": re.sub(r"\s+", " ", item["rationale"].strip()),
            }
            for item in parsed["scores"]
        ],
        "total": parsed["published_total"],
        "tier": parsed["published_tier"],
        "special": re.sub(r"\s+", " ", special_match.group(1).strip()) if special_match else "",
        "notes": re.sub(r"\s+", " ", notes_match.group(1).strip()) if notes_match else "",
    }


def aggregate_hash(paths: Iterable[Path], root: Path) -> tuple[str, list[dict[str, str]]]:
    entries = [
        {"path": path.resolve().relative_to(root.resolve()).as_posix(), "sha256": sha256_file(path)}
        for path in sorted(paths)
    ]
    return sha256_bytes(yaml_bytes(entries)), entries
