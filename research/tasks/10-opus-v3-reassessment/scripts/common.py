#!/usr/bin/env python3
"""Shared Task 10 engine: v3 rubric view, prompt, output schema, sandboxed call and conversion.

Package hashing, YAML serialization, Git access and tier arithmetic come from the
Task 05 engine through ``engine_adapter``; this module adds only what the
Claude Code runner and checklist revision 3 need.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from engine_adapter import REPO_ROOT, TASK05_ROOT, TASK_ROOT, output_engine, package_engine


TASK_ID = "10-opus-v3-reassessment"
CONFIG_PATH = TASK_ROOT / "config.yaml"
TASK_CONTRACT = TASK_ROOT / "TASK.md"
SYSTEM_PROMPT = TASK_ROOT / "prompts" / "system.md"
ASSESSMENT_CONTRACT = TASK_ROOT / "prompts" / "assessment-contract.md"
RUBRIC_ROOT = TASK_ROOT / "inputs" / "rubric"
TASK05_TEMPLATE = TASK05_ROOT / "templates" / "output.yaml"
TRANSFORMATION = "remove_revision_notes_v1"
ISOLATION_METHOD = "bubblewrap_claude_p_no_tools_v1"
CONFIDENCE = ["low", "medium", "high"]
INTERACTION_KINDS = ["coordinated_cases", "local_compatibility_check"]
XEIP = "cross_eip_interactions"
ATTESTATION = (
    "Launcher attestation: one tool-less claude -p call in a bubblewrap capsule with no tools, MCP "
    "servers, skills or project files; the prompt contained only the sealed package documents. The "
    "model was instructed not to use remembered facts; recall itself cannot be technically excluded."
)
FORK_NAMES = {
    "paris": "Paris (The Merge)",
    "shanghai": "Shanghai",
    "cancun": "Cancun",
    "prague": "Prague",
    "osaka": "Osaka",
    "amsterdam": "Amsterdam (Glamsterdam)",
    "hegota": "Hegotá",
}

load_yaml = package_engine.load_yaml
yaml_bytes = package_engine.yaml_bytes
sha256 = package_engine.sha256
file_sha256 = package_engine.file_sha256
write_bytes = package_engine.write_bytes
InputError = package_engine.InputError


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def task_rel(path: Path) -> str:
    return path.resolve().relative_to(TASK_ROOT).as_posix()


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def config() -> dict[str, Any]:
    return load_yaml(CONFIG_PATH)


# --- Rubric -------------------------------------------------------------------------------


def transform_rubric_v3(source: bytes) -> bytes:
    """Drop the Revision Notes, which carry calibration scores for EIP-7928, and the link to them."""
    text = source.decode()
    start = text.find("##### Revision Notes")
    end = text.find("\n## ", start)
    if start < 0 or end < 0:
        raise InputError("Pinned v3 rubric no longer has the expected Revision Notes boundary")
    view = text[:start].rstrip() + "\n" + text[end:]
    view, count = re.subn(r" — see \[Revision Notes\]\(#revision-notes\)", "", view)
    if count != 1:
        raise InputError("Expected exactly one Revision Notes link in the v3 rubric")
    for leak in ("Amsterdam calibration", "proposed-anchors.md", "EIP-7928", "Revision Notes"):
        if leak in view:
            raise InputError(f"Calibration material leaked into the assessor view: {leak}")
    return view.encode()


def parse_rubric(view: str) -> dict[str, Any]:
    """Criteria, permitted levels, exceptional score, cross-EIP bonus rule and tiers, from the template text."""
    blocks = re.split(r"^##### ", view, flags=re.M)[1:]
    criteria = []
    for block in blocks:
        heading = block.splitlines()[0]
        match = re.fullmatch(r"(\S+) — (.+)", heading.strip())
        if not match:
            continue
        levels = [int(item) for item in re.findall(r"^- (\d)\. ", block, flags=re.M)]
        criteria.append({"abbreviation": match.group(1), "label": match.group(2), "levels": levels})
    exceptional = re.search(r"A score of (\d) may be used in exceptional circumstances", view)
    bonus = re.search(
        r"\*\*\+(\d) for every (\d) additional interacting EIPs beyond the first (\d)\*\*", view
    )
    low = re.search(r"\*\*Low Complexity\*\* \| \*\*<(\d+)\*\*", view)
    high = re.search(r"\*\*High Complexity\*\* \| \*\*>=(\d+)\*\*", view)
    revision = re.search(r"Checklist revision: \*\*(\d+)\*\*", view)
    if not (exceptional and bonus and low and high and revision) or len(criteria) != 28:
        raise InputError("Could not parse the v3 rubric's criteria, exceptional score, bonus or tiers")
    template = load_yaml(TASK05_TEMPLATE)
    for criterion, expected in zip(criteria, template["criteria"]):
        if criterion["label"] != expected["label"]:
            raise InputError(f"v3 criterion order or label differs: {criterion['label']}")
        criterion["id"] = expected["id"]
        if not criterion["levels"] or criterion["levels"][0] != 0:
            raise InputError(f"No levels parsed for {criterion['label']}")
    return {
        "checklist_revision": int(revision.group(1)),
        "criteria": criteria,
        "exceptional_score": int(exceptional.group(1)),
        "bonus": {
            "increment": int(bonus.group(1)),
            "per_additional": int(bonus.group(2)),
            "beyond_first": int(bonus.group(3)),
        },
        "tiers": {"medium_from": int(low.group(1)), "high_from": int(high.group(1))},
    }


def check_tiers_match_engine(rubric: dict[str, Any]) -> None:
    """The v3 thresholds must equal the Task 05 engine's, so its tier arithmetic is reused unchanged."""
    medium, high = rubric["tiers"]["medium_from"], rubric["tiers"]["high_from"]
    probes = {medium - 1: "low", medium: "medium", high - 1: "medium", high: "high"}
    for total, expected in probes.items():
        if output_engine.tier(total) != expected:
            raise InputError("v3 tier thresholds differ from the Task 05 engine")


def permitted_levels(rubric: dict[str, Any], criterion_id: str) -> list[int]:
    criterion = next(item for item in rubric["criteria"] if item["id"] == criterion_id)
    return sorted({*criterion["levels"], rubric["exceptional_score"]})


def cross_eip_bonus(rubric: dict[str, Any], qualifying: int) -> int:
    rule = rubric["bonus"]
    return rule["increment"] * (max(0, qualifying - rule["beyond_first"]) // rule["per_additional"])


def rubric_material(pm_repo: Path) -> tuple[bytes, bytes, dict[str, Any]]:
    expected = config()["rubric"]
    source, blob = package_engine.git_blob(pm_repo, expected["repository_commit"], expected["path"])
    if blob != expected["git_blob_sha"]:
        raise InputError(f"Rubric Git blob mismatch: {blob}")
    if sha256(source) != expected["content_sha256"]:
        raise InputError("Rubric content SHA-256 mismatch")
    view = transform_rubric_v3(source)
    if sha256(view) != config()["assessor_view"]["content_sha256"]:
        raise InputError(f"Assessor view hash differs from config: {sha256(view)}")
    rubric = parse_rubric(view.decode())
    check_tiers_match_engine(rubric)
    manifest = {
        "schema_version": 1,
        "source": copy.deepcopy(expected),
        "source_file": {"path": rel(RUBRIC_ROOT / "source.md"), "content_sha256": sha256(source)},
        "assessor_view": {
            "path": rel(RUBRIC_ROOT / "assessor-view.md"),
            "content_sha256": sha256(view),
            "transformation": TRANSFORMATION,
            "normative_criteria_preserved": True,
            "tier_definitions_preserved": True,
        },
        "parsed": rubric,
    }
    return source, view, manifest


def frozen_rubric() -> tuple[str, dict[str, Any]]:
    manifest = load_yaml(RUBRIC_ROOT / "manifest.yaml")
    view_path = RUBRIC_ROOT / "assessor-view.md"
    if file_sha256(view_path) != manifest["assessor_view"]["content_sha256"]:
        raise InputError("Frozen assessor view changed")
    view = view_path.read_text(encoding="utf-8")
    if parse_rubric(view) != manifest["parsed"]:
        raise InputError("Frozen parsed rubric differs from the assessor view")
    return view, manifest


# --- Prompt and schema --------------------------------------------------------------------

EIP_MENTION_RE = re.compile(r"\b(?:EIP|ERC)-(\d+)\b|\beip-(\d+)\.md\b", re.IGNORECASE)


def candidate_eips(eip_text: str, number: int) -> list[int]:
    """Every other EIP the target names in its text or `requires`; the cross-EIP list is limited to these."""
    found = {int(a or b) for a, b in EIP_MENTION_RE.findall(eip_text)}
    found |= package_engine.required_eips(eip_text)
    found.discard(number)
    return sorted(found)


def render_prompt(
    *,
    identity: str,
    documents: list[tuple[str, str, str]],
    rubric_view: str,
    candidates: list[int],
) -> str:
    """Documents (path, role, text), then the template, the candidate list and the task."""
    lines = ["# Documents", "", identity, "", "Supplied documents:"]
    lines += [f"- `{path}` ({role})" for path, role, _ in documents]
    for path, role, text in documents:
        lines.append(f'\n<document path="{path}" role="{role}">\n{text}\n</document>')
    lines.append(
        f'\n# Assessment template\n\n<document path="rubric.md" role="template">\n{rubric_view}\n</document>'
    )
    named = ", ".join(f"EIP-{item}" for item in candidates) or "none"
    lines.append(f"\n# Candidate interacting EIPs\n\n{named}")
    lines.append("\n# Task\n\n" + ASSESSMENT_CONTRACT.read_text(encoding="utf-8"))
    return "\n".join(lines)


def obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def enum(values: list[Any]) -> dict[str, Any]:
    return {"type": "string" if isinstance(values[0], str) else "integer", "enum": values}


def output_schema(rubric: dict[str, Any], sources: list[str], candidates: list[int]) -> dict[str, Any]:
    evidence = {
        "type": "array",
        "items": obj({"source": enum(sources), "locator": {"type": "string"}, "summary": {"type": "string"}}),
    }
    text = {"type": "string"}
    criteria = {
        item["id"]: obj(
            {
                "score": enum(permitted_levels(rubric, item["id"])),
                "evidence": evidence,
                "rationale": text,
                "confidence": enum(CONFIDENCE),
                "uncertainty_note": text,
                "exceptional_score_justification": text,
            }
        )
        for item in rubric["criteria"]
    }
    interacting = (
        {
            "type": "array",
            "items": obj(
                {"eip": enum(candidates), "interaction": enum(INTERACTION_KINDS), "coordinated_cases": text}
            ),
        }
        if candidates
        else {"type": "array", "maxItems": 0, "items": obj({"eip": {"type": "integer"}})}
    )
    ids = [item["id"] for item in rubric["criteria"]]
    return obj(
        {
            "scope_summary": text,
            "criteria": obj(criteria),
            "cross_eip": obj(
                {"interacting_eips": interacting, "unidentified_interactions": {"type": "array", "items": text}}
            ),
            "under_specification": obj(
                {
                    "present": {"type": "boolean"},
                    "summary": text,
                    "affected_criteria": {
                        "type": "array",
                        "items": obj(
                            {
                                "criterion": enum(ids),
                                "minimum_score": {"type": "integer"},
                                "maximum_score": {"type": "integer"},
                            }
                        ),
                    },
                    "unresolved_questions": {"type": "array", "items": text},
                }
            ),
            "notable_ambiguities": {"type": "array", "items": text},
            "overall_confidence": enum(CONFIDENCE),
        }
    )


def schema_bytes(schema: dict[str, Any]) -> bytes:
    return (json.dumps(schema, indent=1, sort_keys=False) + "\n").encode()


# --- Sandboxed claude -p --------------------------------------------------------------------


def claude_binary() -> Path:
    return Path(shutil.which("claude") or "").resolve()


def claude_version() -> str:
    return subprocess.run(
        [str(claude_binary()), "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()


def claude_command(runtime: dict[str, Any], system_prompt: str, schema: dict[str, Any]) -> list[str]:
    """A tool-less `claude -p` in a bubblewrap capsule whose home holds only the login credential."""
    binary = claude_binary()
    home = Path.home()
    credential = home / ".claude" / ".credentials.json"
    if not binary.is_file() or not credential.is_file():
        raise InputError("claude CLI and a logged-in ~/.claude/.credentials.json are required")
    capsule = [
        "bwrap", "--unshare-pid", "--unshare-ipc", "--unshare-uts", "--unshare-cgroup",
        "--die-with-parent", "--new-session",
        "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
        "--symlink", "usr/bin", "/bin", "--symlink", "usr/sbin", "/sbin",
        "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf", "--ro-bind", "/etc/ssl", "/etc/ssl",
        "--ro-bind-try", "/etc/ca-certificates", "/etc/ca-certificates",
        "--ro-bind-try", "/etc/nsswitch.conf", "/etc/nsswitch.conf",
        "--ro-bind-try", "/etc/hosts", "/etc/hosts",
        "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--tmpfs", "/home",
        "--dir", str(home / ".claude"), "--bind", str(credential), str(credential),
        "--ro-bind", str(binary), "/opt/claude", "--dir", "/work", "--chdir", "/work",
        "--clearenv", "--setenv", "HOME", str(home), "--setenv", "PATH", "/usr/bin",
        "--setenv", "TERM", "dumb",
    ]  # fmt: skip
    return capsule + [
        "/opt/claude", *runtime["claude_flags"], "--model", runtime["model"], "--effort", runtime["effort"],
        "--system-prompt", system_prompt, "--json-schema", json.dumps(schema),
    ]  # fmt: skip


def call(runtime: dict[str, Any], system_prompt: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    command = claude_command(runtime, system_prompt, schema)
    started = now()
    try:
        proc = subprocess.run(
            command, input=prompt, capture_output=True, text=True, timeout=runtime["timeout_seconds"]
        )
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr, code = "", f"timeout after {error.timeout} s", -1
    record: dict[str, Any] = {
        "started_at": started,
        "finished_at": now(),
        "exit_code": code,
        "stderr": stderr[-4000:],
        "prompt_sha256": sha256(prompt.encode()),
        "system_prompt_sha256": sha256(system_prompt.encode()),
        "schema_sha256": sha256(schema_bytes(schema)),
    }
    try:
        record["output"] = json.loads(stdout)
    except json.JSONDecodeError:
        record["output"] = None
        record["stdout"] = stdout[-4000:]
    out = record["output"] or {}
    record["ok"] = code == 0 and not out.get("is_error") and isinstance(out.get("structured_output"), dict)
    return record


# --- Conversion to the Task 05 assessment shape ---------------------------------------------


def convert(
    *,
    raw: dict[str, Any],
    raw_path: Path,
    template: dict[str, Any],
    rubric: dict[str, Any],
    candidates: list[int],
    scope_field: str,
    runtime: dict[str, Any],
) -> dict[str, Any]:
    """Map one structured response onto the sealed output template; totals and tiers are computed here."""
    out = raw["output"]["structured_output"]
    result = copy.deepcopy(template)
    result["assessment"] = {scope_field: out["scope_summary"].strip()}
    scores: dict[str, int] = {}
    for criterion in result["criteria"]:
        answer = out["criteria"][criterion["id"]]
        score = answer["score"]
        if score not in permitted_levels(rubric, criterion["id"]):
            raise InputError(f"{criterion['id']}: level {score} is not permitted")
        criterion["score"] = score
        criterion["evidence"] = [
            {"source": item["source"], "locator": item["locator"].strip(), "summary": item["summary"].strip()}
            for item in answer["evidence"]
        ]
        criterion["rationale"] = answer["rationale"].strip()
        criterion["confidence"] = answer["confidence"]
        criterion["uncertainty_note"] = answer["uncertainty_note"].strip() or "None identified."
        justification = answer["exceptional_score_justification"].strip()
        criterion["exceptional_score_justification"] = justification or None
        scores[criterion["id"]] = score

    xeip = next(item for item in result["criteria"] if item["id"] == XEIP)
    details = []
    seen: set[int] = set()
    for item in out["cross_eip"]["interacting_eips"]:
        if item["eip"] in seen or item["eip"] not in candidates:
            continue
        seen.add(item["eip"])
        details.append(
            {"eip": item["eip"], "interaction": item["interaction"], "cases": item["coordinated_cases"].strip()}
        )
    qualifying = [item["eip"] for item in details if item["interaction"] == "coordinated_cases"]
    bonus = cross_eip_bonus(rubric, len(qualifying))
    xeip["base_score"] = scores[XEIP]
    xeip["bonus"] = bonus
    xeip["score"] = scores[XEIP] + bonus
    scores[XEIP] = xeip["score"]
    xeip["interacting_eips"] = [item["eip"] for item in details]
    xeip["bonus_qualifying_eips"] = qualifying
    xeip["interaction_details"] = details
    xeip["unidentified_interactions"] = (
        [text.strip() for text in out["cross_eip"]["unidentified_interactions"] if text.strip()]
        if xeip["base_score"] > 0
        else []
    )

    total = sum(scores.values())
    result["totals"] = {"primary_score": total, "complexity_tier": output_engine.tier(total)}

    under = out["under_specification"]
    affected: dict[str, tuple[int, int]] = {}
    for item in under["affected_criteria"]:
        score = scores[item["criterion"]] if item["criterion"] != XEIP else xeip["base_score"]
        low = min(item["minimum_score"], item["maximum_score"], score)
        high = max(item["minimum_score"], item["maximum_score"], score)
        affected[item["criterion"]] = (low - score, high - score)
    minimum = total + sum(delta for delta, _ in affected.values())
    maximum = total + sum(delta for _, delta in affected.values())
    ordered = [item["id"] for item in result["criteria"] if item["id"] in affected]
    result["under_specification"] = {
        "present": bool(under["present"]),
        "summary": under["summary"].strip(),
        "affected_criteria": ordered,
        "criterion_ranges": [
            {
                "criterion": key,
                "minimum_score": affected[key][0] + (xeip["base_score"] if key == XEIP else scores[key]),
                "maximum_score": affected[key][1] + (xeip["base_score"] if key == XEIP else scores[key]),
            }
            for key in ordered
        ],
        "plausible_total_range": {"minimum": max(0, minimum), "maximum": maximum},
        "plausible_tiers": output_engine.tiers_in_range(max(0, minimum), maximum),
        "unresolved_questions": [text.strip() for text in under["unresolved_questions"] if text.strip()],
    }
    result["notable_ambiguities"] = [text.strip() for text in out["notable_ambiguities"] if text.strip()]
    result["overall_confidence"] = out["overall_confidence"]
    control = result.get("hindsight_control") or result["information_control"]
    control["attestation"] = ATTESTATION

    output = raw["output"]
    assessor = result["provenance"]["assessor"]
    assessor["run_at"] = raw["started_at"]
    assessor["session_id"] = raw["run_id"]
    assessor["session_id_source"] = "isolated_launcher_run_id"
    assessor["isolation_method"] = ISOLATION_METHOD
    assessor["agent_identity"] = f"Claude Code {raw['claude_code_version']} headless (claude -p, no tools)"
    result["provenance"]["engine"] = {
        "claude_code_version": raw["claude_code_version"],
        "claude_flags": list(runtime["claude_flags"]),
        "model": runtime["model"],
        "effort": runtime["effort"],
        "advisor_model": None,
        "fallback_model": None,
        "system_prompt_sha256": raw["system_prompt_sha256"],
        "prompt_sha256": raw["prompt_sha256"],
        "schema_sha256": raw["schema_sha256"],
        "started_at": raw["started_at"],
        "finished_at": raw["finished_at"],
        "duration_ms": output.get("duration_ms"),
        "num_turns": output.get("num_turns"),
        "usage": output.get("usage"),
        "model_usage": output.get("modelUsage"),
        "total_cost_usd": output.get("total_cost_usd"),
    }
    result["provenance"]["assessor_raw_output"] = {
        "path": task_rel(raw_path),
        "content_sha256": file_sha256(raw_path),
    }
    result["provenance"]["postprocessing"] = [
        "Mapped the schema-constrained structured_output onto the sealed output template without changing any level, evidence entry or rationale; whitespace was trimmed.",
        "Cross-EIP interactions: score = model base level + mechanical bonus (+1 per 3 coordinated-case EIPs beyond the first 3, from the rubric); interacting EIPs are limited to the sealed candidate list and deduplicated.",
        "Totals, tier and plausible total range were computed from criterion levels and per-criterion ranges; a stated range is widened to include the primary level.",
    ]
    return result
