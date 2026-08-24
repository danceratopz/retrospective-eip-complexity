#!/usr/bin/env python3
"""Render Task 04 assessment-ref proposals over Task 03 EL timelines."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import sys
from pathlib import Path
from typing import Any

import yaml


TASK_ID = "04-complexity-assessment-ref-selection"
TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK03_ROOT = REPO_ROOT / "research" / "tasks" / "03-fork-development-timelines"
TASK03_RENDERER = TASK03_ROOT / "scripts" / "render.py"
TASK03_INPUTS = TASK03_ROOT / "inputs" / "forks"
REF_ROOT = TASK_ROOT / "outputs" / "fork-eips"
OUTPUT_ROOT = TASK_ROOT / "outputs" / "review"


def load_renderer() -> Any:
    spec = importlib.util.spec_from_file_location("task03_renderer", TASK03_RENDERER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load Task 03 renderer: {TASK03_RENDERER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


renderer = load_renderer()
InputError = renderer.InputError


def revision_commits(eip: dict[str, Any]) -> dict[str, dict[str, Any]]:
    commits = {eip["creation"]["commit"]: eip["creation"]}
    commits.update({event["commit"]: event for event in eip["revisions"]})
    return commits


def short_offset(seconds: int) -> str:
    sign = "+" if seconds > 0 else ""
    days = seconds / 86_400
    return f"{sign}{days:.2f} days"


def build_markers(
    fork_id: str, dataset: dict[str, Any]
) -> tuple[list[dict[str, Any]], set[Path]]:
    ref_dir = REF_ROOT / fork_id
    paths = sorted(ref_dir.glob("eip-*.yaml"))
    if not paths:
        raise InputError(f"No Task 04 records found under {ref_dir}")

    execution_eips = {
        int(eip["number"]): eip
        for eip in dataset["eips"]
        if "execution" in eip["layers"]
    }
    found: set[int] = set()
    markers: list[dict[str, Any]] = []

    for path in paths:
        record = renderer.load_yaml(path)
        if record.get("task_id") != TASK_ID or record.get("fork_id") != fork_id:
            raise InputError(f"Unexpected Task 04 identity in {path}")
        number = int(record["eip"]["number"])
        if number not in execution_eips:
            raise InputError(f"Task 04 record is not execution-affecting: EIP-{number}")
        if number in found:
            raise InputError(f"Duplicate Task 04 record for EIP-{number}")
        found.add(number)

        eip = execution_eips[number]
        selected = record["selection"]["selected_revision"]
        candidates = revision_commits(eip)
        if selected["commit"] not in candidates:
            raise InputError(
                f"EIP-{number} selected commit is absent from Task 03 history: "
                f"{selected['commit']}"
            )
        selected_event = candidates[selected["commit"]]
        if renderer.parse_datetime(selected_event["occurred_at"]) != renderer.parse_datetime(
            selected["committed_at"]
        ):
            raise InputError(f"EIP-{number} selected-ref timestamp mismatch")

        anchor = record["anchor"]
        anchor_matches = [
            event
            for event in eip["inclusions"]
            if event["id"] == anchor["selected_event_id"]
        ]
        if len(anchor_matches) != 1:
            raise InputError(
                f"EIP-{number} anchor event does not resolve uniquely in Task 03 data"
            )
        anchor_event = anchor_matches[0]
        if renderer.parse_datetime(anchor_event["occurred_at"]) != renderer.parse_datetime(
            anchor["effective_at"]
        ):
            raise InputError(f"EIP-{number} anchor timestamp mismatch")

        review_status = record["review"]["status"]
        common = {
            "eip": number,
            "anchor_kind": anchor["kind"],
            "selection_mode": record["selection"]["mode"],
            "review_status": review_status,
        }
        markers.append(
            {
                **common,
                "marker_kind": "Selected assessment ref",
                "occurred_at": selected["committed_at"],
                "event_label": f"Selected ref · {selected['commit'][:12]}",
                "offset_from_anchor": short_offset(
                    int(selected["offset_from_anchor_seconds"])
                ),
                "commit": selected["commit"],
                "rationale": record["selection"]["rationale"],
                "source_url": selected["immutable_url"],
            }
        )
        markers.append(
            {
                **common,
                "marker_kind": "Proposal anchor",
                "occurred_at": anchor["effective_at"],
                "event_label": anchor["raw_label"],
                "offset_from_anchor": "0.00 days",
                "commit": "",
                "rationale": anchor["date_basis"],
                "source_url": anchor_event["source_url"],
            }
        )

    missing = sorted(set(execution_eips) - found)
    extra = sorted(found - set(execution_eips))
    if missing or extra:
        raise InputError(
            f"Task 04 inventory mismatch for {fork_id}: missing={missing}, extra={extra}"
        )
    return markers, set(paths)


def render(fork_id: str, *, validate_only: bool) -> None:
    config_path = TASK03_INPUTS / f"{fork_id}.yaml"
    if not config_path.is_file():
        raise InputError(f"Missing Task 03 fork input: {config_path}")
    dataset, task03_files = renderer.load_fork(config_path)
    markers, task04_files = build_markers(fork_id, dataset)
    dataset["assessment_ref_markers"] = markers
    if validate_only:
        print(
            f"validated {fork_id}: "
            f"selected_refs={len(markers) // 2}, markers={len(markers)}"
        )
        return

    output_dir = OUTPUT_ROOT / fork_id
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / "plot-data.json"
    renderer.write_text(
        data_path, renderer.json_text(renderer.exportable_dataset(dataset))
    )
    artifacts = [data_path]
    artifacts.extend(
        renderer.render_chart(
            renderer.style(renderer.layer_chart(dataset, "execution")),
            output_dir / "el-assessment-ref-review",
        )
    )

    reproducibility_files = {
        TASK03_ROOT / "pyproject.toml",
        TASK03_ROOT / "uv.lock",
        TASK03_RENDERER,
        Path(__file__).resolve(),
        *task03_files,
        *task04_files,
    }
    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "artifact": "assessment-ref-review-timeline",
        "fork_id": fork_id,
        "determinism": {
            "generation_timestamp_recorded": False,
            "offline_html": True,
            "canonical_visual_specification": "Vega-Lite JSON",
            "task_03_renderer_reused": True,
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
            "execution_eips": len(markers) // 2,
            "selected_ref_markers": sum(
                marker["marker_kind"] == "Selected assessment ref"
                for marker in markers
            ),
            "proposal_anchor_markers": sum(
                marker["marker_kind"] == "Proposal anchor" for marker in markers
            ),
            "needs_human_review": sum(
                marker["marker_kind"] == "Selected assessment ref"
                and marker["review_status"] == "needs_human_review"
                for marker in markers
            ),
        },
    }
    manifest_path = output_dir / "plot-manifest.yaml"
    renderer.write_text(
        manifest_path,
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=100),
    )
    print(
        f"rendered {fork_id}: "
        f"selected_refs={len(markers) // 2}, markers={len(markers)}"
    )


def configured_forks() -> list[str]:
    return sorted(
        path.name for path in REF_ROOT.iterdir() if path.is_dir() and list(path.glob("eip-*.yaml"))
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fork",
        action="append",
        choices=configured_forks(),
        help="Fork to render; repeat for multiple forks. Defaults to every configured fork.",
    )
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    forks = args.fork or configured_forks()
    if not forks:
        raise InputError(f"No Task 04 output directories found under {REF_ROOT}")
    for fork_id in forks:
        render(fork_id, validate_only=args.validate_only)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as error:
        print(f"input error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
