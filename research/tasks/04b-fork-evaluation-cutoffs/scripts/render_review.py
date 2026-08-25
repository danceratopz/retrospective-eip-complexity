#!/usr/bin/env python3
"""Render Task 04b cutoffs over approved Task 04 EL review timelines."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

import yaml


TASK_ID = "04b-fork-evaluation-cutoffs"
TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK03_ROOT = REPO_ROOT / "research" / "tasks" / "03-fork-development-timelines"
TASK04_ROOT = REPO_ROOT / "research" / "tasks" / "04-complexity-assessment-ref-selection"
TASK03_INPUTS = TASK03_ROOT / "inputs" / "forks"
CUTOFF_ROOT = TASK_ROOT / "outputs" / "forks"
OUTPUT_ROOT = TASK_ROOT / "outputs" / "review"


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


renderer = load_module("task03_renderer", TASK03_ROOT / "scripts" / "render.py")
ref_review = load_module("task04_review", TASK04_ROOT / "scripts" / "render_review.py")
InputError = renderer.InputError


def source_url(record: dict[str, Any]) -> str:
    registry = renderer.load_yaml(REPO_ROOT / record["inputs"]["task01_source_registry"])
    sources = {source["id"]: source for source in registry["sources"]}
    for source_id in record["cutoff"]["source_ids"]:
        source = sources.get(source_id)
        if source:
            return source.get("immutable_url") or source.get("canonical_url") or ""
    return ""


def cutoff_markers(record: dict[str, Any]) -> list[dict[str, Any]]:
    cutoff = record["cutoff"]
    url = source_url(record)
    markers = []
    for entry in record["eips"]:
        cohort = (
            "Forecastable at cutoff"
            if entry["cohort"] == "forecastable_at_cutoff"
            else "Late scope"
        )
        late_note = ""
        if entry["late_scope"]:
            late_note = (
                f" Late classification: {entry['late_scope']['classification']}. "
                f"{entry['late_scope']['rationale']}"
            )
        markers.append(
            {
                "eip": int(entry["number"]),
                "marker_kind": "Fork evaluation cutoff",
                "occurred_at": cutoff["effective_at"],
                "event_label": cutoff["label"],
                "anchor_kind": "fork_scope",
                "selection_mode": "aggregation_cohort",
                "offset_from_anchor": "not applicable",
                "commit": "",
                "review_status": record["review"]["status"],
                "cohort": cohort,
                "rationale": (
                    f"{cutoff['rationale']} This EIP is classified as {cohort.lower()} "
                    f"from Task 01 event {entry['scope_basis_event_id']} at "
                    f"{entry['scope_basis_occurred_at']}.{late_note}"
                ),
                "source_url": url,
            }
        )
    return markers


def render(fork_id: str, *, validate_only: bool) -> None:
    config_path = TASK03_INPUTS / f"{fork_id}.yaml"
    cutoff_path = CUTOFF_ROOT / f"{fork_id}.yaml"
    if not config_path.is_file() or not cutoff_path.is_file():
        raise InputError(f"missing Task 03 or Task 04b input for {fork_id}")
    dataset, task03_files = renderer.load_fork(config_path)
    ref_markers, task04_files = ref_review.build_markers(fork_id, dataset)
    cutoff_record = renderer.load_yaml(cutoff_path)
    if cutoff_record.get("task_id") != TASK_ID or cutoff_record.get("fork_id") != fork_id:
        raise InputError(f"unexpected Task 04b identity in {cutoff_path}")
    cutoff = cutoff_markers(cutoff_record)
    execution_numbers = {
        int(eip["number"])
        for eip in dataset["eips"]
        if "execution" in eip["layers"]
    }
    if {marker["eip"] for marker in cutoff} != execution_numbers:
        raise InputError(f"Task 04b execution inventory mismatch for {fork_id}")
    dataset["assessment_ref_markers"] = [*ref_markers, *cutoff]

    marker_times = [
        renderer.parse_datetime(marker["occurred_at"])
        for marker in dataset["assessment_ref_markers"]
    ]
    original_start = renderer.parse_datetime(dataset["plot"]["start_date"])
    original_end = renderer.parse_datetime(dataset["plot"]["end_date"])
    earliest = min(marker_times)
    latest = max(marker_times)
    if earliest < original_start:
        dataset["plot"]["start_date"] = (earliest - timedelta(days=14)).date().isoformat()
    if latest > original_end:
        dataset["plot"]["end_date"] = (latest + timedelta(days=14)).date().isoformat()
    dataset["plot"]["notes"].append(
        "Task 04b adds the proposed fork evaluation cutoff and aggregation cohort to each EL panel."
    )

    if validate_only:
        late_count = sum(entry["cohort"] == "late_scope" for entry in cutoff_record["eips"])
        print(
            f"validated {fork_id}: eips={len(cutoff)}, late_scope={late_count}, "
            f"cutoff={cutoff_record['cutoff']['effective_at']}"
        )
        return

    output_dir = OUTPUT_ROOT / fork_id
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / "plot-data.json"
    renderer.write_text(data_path, renderer.json_text(renderer.exportable_dataset(dataset)))
    artifacts = [data_path]
    artifacts.extend(
        renderer.render_chart(
            renderer.style(renderer.layer_chart(dataset, "execution")),
            output_dir / "el-evaluation-cutoff-review",
        )
    )
    reproducibility_files = {
        TASK03_ROOT / "pyproject.toml",
        TASK03_ROOT / "uv.lock",
        TASK03_ROOT / "scripts" / "render.py",
        TASK04_ROOT / "scripts" / "render_review.py",
        TASK04_ROOT / "outputs" / "anchor-fallback-policy.yaml",
        TASK_ROOT / "TASK.md",
        TASK_ROOT / "outputs" / "aggregation-policy.yaml",
        Path(__file__).resolve(),
        cutoff_path,
        *task03_files,
        *task04_files,
    }
    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "artifact": "fork-evaluation-cutoff-review-timeline",
        "fork_id": fork_id,
        "determinism": {
            "generation_timestamp_recorded": False,
            "offline_html": True,
            "canonical_visual_specification": "Vega-Lite JSON",
            "task_03_renderer_reused": True,
            "task_04_markers_reused": True,
        },
        "toolchain": {
            "python": (
                f"{sys.version_info.major}.{sys.version_info.minor}."
                f"{sys.version_info.micro}"
            ),
            "altair": importlib.metadata.version("altair"),
            "cairosvg": importlib.metadata.version("cairosvg"),
            "vl-convert-python": importlib.metadata.version("vl-convert-python"),
            "pyyaml": importlib.metadata.version("pyyaml"),
        },
        "inputs": [
            {"path": renderer.rel(path), "sha256": renderer.file_sha256(path)}
            for path in sorted(reproducibility_files)
        ],
        "outputs": [
            {
                "path": artifact.relative_to(output_dir).as_posix(),
                "sha256": renderer.file_sha256(artifact),
                "bytes": artifact.stat().st_size,
            }
            for artifact in sorted(artifacts)
        ],
        "counts": {
            "execution_eips": len(cutoff),
            "forecastable_at_cutoff": sum(
                entry["cohort"] == "forecastable_at_cutoff"
                for entry in cutoff_record["eips"]
            ),
            "late_scope": sum(
                entry["cohort"] == "late_scope" for entry in cutoff_record["eips"]
            ),
            "cutoff_markers": len(cutoff),
        },
        "cutoff": cutoff_record["cutoff"],
        "review_status": cutoff_record["review"]["status"],
    }
    manifest_path = output_dir / "plot-manifest.yaml"
    renderer.write_text(
        manifest_path,
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=100),
    )
    print(
        f"rendered {fork_id}: eips={len(cutoff)}, "
        f"cutoff={cutoff_record['cutoff']['effective_at']}"
    )


def configured_forks() -> list[str]:
    return sorted(path.stem for path in CUTOFF_ROOT.glob("*.yaml"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fork",
        action="append",
        choices=configured_forks(),
        help="Fork to render; repeat for multiple forks. Defaults to all configured forks.",
    )
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for fork_id in args.fork or configured_forks():
        render(fork_id, validate_only=args.validate_only)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as error:
        print(f"input error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
