"""Shared paths, constants, and helpers for the publication adapter."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / "publication/site/public/generated"
CONTRACT = ROOT / "publication/contract"
TASK04B_CUTOFFS = ROOT / "research/tasks/04b-fork-evaluation-cutoffs/outputs/forks"
TASK04B_TIMELINES = ROOT / "research/tasks/04b-fork-evaluation-cutoffs/outputs/review"
TASK03_INPUTS = ROOT / "research/tasks/03-fork-development-timelines/inputs/forks"
TASK05 = ROOT / "research/tasks/05-retrospective-complexity-assignment"
TASK05_OUTPUTS = TASK05 / "outputs/fork-eips"
TASK05_RUBRIC = TASK05 / "inputs/rubric"
TASK05C = ROOT / "research/tasks/05c-amsterdam-human-assessment-alignment"
TASK07_JOIN = ROOT / "research/tasks/07-observed-effort-metrics/outputs/join"
TASK08 = ROOT / "research/tasks/08-hegota-prospective-complexity-assessment"
TASK08_OUTPUTS = TASK08 / "outputs"
TASK08_EXTENSION = TASK08 / "extensions/sfi-cfi-2026-08-26/outputs"
TASK09 = ROOT / "research/tasks/09-hegota-human-assessment-snapshot/outputs"

VERSION = "2.0.0"
FORK_ORDER = ["shanghai", "cancun", "prague", "osaka", "amsterdam", "hegota"]
RETROSPECTIVE_FORKS = FORK_ORDER[:-1]
PROSPECTIVE_FORK = "hegota"
FORK_NAMES = {
    "shanghai": "Shanghai / Shapella",
    "cancun": "Cancun / Dencun",
    "prague": "Prague / Pectra",
    "osaka": "Osaka / Fusaka",
    "amsterdam": "Amsterdam / Glamsterdam",
    "hegota": "Hegotá",
}
FORK_SHORT_NAMES = {fork: name.split(" / ")[0] for fork, name in FORK_NAMES.items()}
PROJECTED_MAINNET = {"amsterdam": "2026-12-15"}
MULTI_EL_FIRST_DEVNET = {"cancun": "dencun-devnet-4"}

SOURCE_LLM = "llm"
SOURCE_HUMAN = "human"
# Assessment and human-source statuses share one vocabulary so the site can render one badge component.
STATUS_COMPLETE = "complete"
STATUS_AVAILABLE_IN_OPEN_PR = "available_in_open_pr"
STATUS_IN_PROGRESS = "in_progress"
STATUS_INCOMPLETE = "incomplete"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_NOT_AVAILABLE = "not_available"
ASSESSMENT_STATUSES = [
    STATUS_COMPLETE,
    STATUS_AVAILABLE_IN_OPEN_PR,
    STATUS_IN_PROGRESS,
    STATUS_INCOMPLETE,
    STATUS_NOT_APPLICABLE,
    STATUS_NOT_AVAILABLE,
]
# Statuses under which an assessment carries a usable total score and criterion scores.
SCORED_STATUSES = {STATUS_COMPLETE, STATUS_AVAILABLE_IN_OPEN_PR, STATUS_IN_PROGRESS}


class BuildError(RuntimeError):
    """Raised when a frozen publication input fails a release invariant."""


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BuildError(f"expected mapping: {path.relative_to(ROOT)}")
    return data


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def source(path: Path) -> dict[str, str]:
    return {"path": relative(path), "sha256": digest(path)}


def github_current_revision(path: str) -> str:
    return f"https://github.com/ethereum/EIPs/blob/master/{path}"


def github_revision_history(path: str) -> str:
    return f"https://github.com/ethereum/EIPs/commits/master/{path}"


def assessment_id(fork: str, eip: int, source_kind: str, revision: int) -> str:
    return f"{fork}:{eip}:{source_kind}:r{revision}"


def occurrence_id(fork: str, eip: int) -> str:
    return f"{fork}:{eip}"


class Sanitizer:
    """Deny-scan a candidate public payload against the adapter boundary contract."""

    def __init__(self) -> None:
        boundary = load_json(CONTRACT / "adapter-boundary.json")["forbidden_public_content"]
        self.forbidden_keys = set(boundary["forbidden_key_names"])
        self.key_patterns = [re.compile(pattern) for pattern in boundary["forbidden_key_patterns"]]
        self.value_patterns = [re.compile(pattern) for pattern in boundary["forbidden_value_patterns"]]

    def check(self, value: Any, path: str = "$") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in self.forbidden_keys or any(pattern.search(key) for pattern in self.key_patterns):
                    raise BuildError(f"forbidden public key {key!r} at {path}")
                self.check(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                self.check(item, f"{path}[{index}]")
        elif isinstance(value, str):
            for pattern in self.value_patterns:
                if pattern.search(value):
                    raise BuildError(f"forbidden public value at {path}: {value[:80]!r}")
