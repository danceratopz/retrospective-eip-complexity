"""Read the explicit, append-only prospective evaluation inventory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import CONTRACT, ROOT, TASK08, BuildError, digest, load_json, load_yaml, source
from .model import llm_assessment


def checked_file(path: str, expected_hash: str, root: Path) -> Path:
    candidate = (ROOT / path).resolve()
    if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
        raise BuildError(f"Evaluation history path is outside its allowed root: {path}")
    if digest(candidate) != expected_hash:
        raise BuildError(f"Evaluation history hash mismatch: {path}")
    return candidate


def load_history(
    originals: list[dict[str, Any]], candidate_eips: set[int]
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    boundary = load_json(CONTRACT / "adapter-boundary.json")["evaluation_history"]
    registry_path = ROOT / boundary["registry"]
    registry = load_yaml(registry_path)
    if registry.get("schema_version") != 1:
        raise BuildError("Unknown evaluation registry schema")
    baseline = {item["id"]: item for item in originals}
    seen: set[str] = set()
    additions = []
    sources = [source(registry_path)]
    for entry in registry["evaluations"]:
        identifier, number, snapshot = entry["id"], entry["eip"], entry["snapshot_id"]
        if identifier in seen or number not in candidate_eips or entry["snapshot_status"] not in {"PFI", "CFI", "SFI"}:
            raise BuildError(f"Duplicate or invalid evaluation entry: {identifier}")
        seen.add(identifier)
        original = baseline.get(identifier)
        if original is None:
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", snapshot):
                raise BuildError("Invalid evaluation snapshot ID")
            if identifier != f"hegota:{number}:llm:r2:{snapshot}":
                raise BuildError("Evaluation ID does not identify its snapshot")
            batch_root = ROOT / boundary["assessment_root"] / snapshot
            path = checked_file(entry["assessment_path"], entry["assessment_sha256"], batch_root / "assessments")
            freeze_path = checked_file(entry["freeze_path"], entry["freeze_sha256"], batch_root)
            validation_path = checked_file(entry["validation_path"], entry["validation_sha256"], batch_root)
            validation = load_yaml(validation_path)
            if validation.get("result") != "pass" or validation.get("snapshot_id") != snapshot or validation.get("assessment_freeze_sha256") != entry["freeze_sha256"]:
                raise BuildError("Evaluation batch has not passed validation")
            sources.append(source(validation_path))
        else:
            if entry["assessment_path"] != original["provenance"]["source_record"]["path"]:
                raise BuildError("Original evaluation path changed")
            path = checked_file(entry["assessment_path"], entry["assessment_sha256"], TASK08)
            freeze_path = checked_file(entry["freeze_path"], entry["freeze_sha256"], TASK08)
        freeze = load_yaml(freeze_path)
        if freeze.get("snapshot_id") != snapshot or freeze.get("assessment_count") != len(freeze["assessments"]):
            raise BuildError("Evaluation freeze identity or count mismatch")
        matches = [item for item in freeze["assessments"] if item["eip"] == number]
        if len(matches) != 1 or any(matches[0][key] != entry[key] for key in ("assessment_path", "assessment_sha256")):
            raise BuildError("Evaluation is absent from its immutable freeze")
        record = load_yaml(path)
        if record.get("task_id") != "08-hegota-prospective-complexity-assessment" or record.get("fork_id") != "hegota" or record.get("snapshot_id") != snapshot or record["eip"]["number"] != number:
            raise BuildError("Evaluation snapshot or EIP mismatch")
        if original is not None:
            if original["snapshot_id"] != snapshot or original["snapshot_status"] != entry["snapshot_status"]:
                raise BuildError("Original evaluation snapshot metadata changed")
        else:
            provenance = record["provenance"]
            rubric = provenance["rubric_source"]
            expected_rubric = originals[0]["provenance"]["rubric"]
            if any(rubric[key] != expected_rubric[key] for key in ("repository", "commit", "path", "immutable_url")) or rubric["checklist_revision"] != 2:
                raise BuildError("Re-evaluation changed the pinned rubric")
            assessor = provenance["assessor"]
            if (assessor["model"], assessor["reasoning_effort"], assessor["isolation_method"]) != ("gpt-5.6-sol", "xhigh", "bubblewrap_one_eip_capsule_v1"):
                raise BuildError("Re-evaluation changed assessor settings")
            control = record["information_control"]
            if any(control.get(key) is not False for key in ("contaminated", "internet_access_attempted", "post_snapshot_information_exposure", "prohibited_source_exposure")):
                raise BuildError("Contaminated evaluation cannot be published")
            revision = provenance["snapshot_eip"]
            if (not re.fullmatch(r"[0-9a-f]{40}", revision["commit"])
                or revision["commit"] != provenance["cohort_snapshot"]["commit"]
                or provenance["cohort_snapshot"]["snapshot_id"] != snapshot
                or revision["repository"] != "ethereum/EIPs"
                or revision["path"] != f"EIPS/eip-{number}.md"
                or revision["immutable_url"] != f"https://github.com/ethereum/EIPs/blob/{revision['commit']}/EIPS/eip-{number}.md"):
                raise BuildError("Evaluation needs a pinned common EIPs commit")
            assessment = llm_assessment(record, path=path, fork="hegota", mode="prospective", revision=2,
                                        role="reevaluation", summary_key="snapshot_scope_summary", eip_key="snapshot_eip",
                                        rubric_key="rubric_source", assessor_key="assessor")
            if assessment["evaluation_date"] is None:
                raise BuildError("New evaluations require a recorded evaluation date")
            assessment.update(id=identifier, snapshot_status=entry["snapshot_status"])
            additions.append(assessment)
        sources.extend([source(path), source(freeze_path)])
    if not set(baseline).issubset(seen):
        raise BuildError("Evaluation registry omitted an original assessment")
    return additions, sources
