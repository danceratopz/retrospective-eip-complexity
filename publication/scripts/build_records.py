#!/usr/bin/env python3
"""Build deterministic, sanitized publication records from frozen research data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "publication/site/public/generated"
TASK05 = ROOT / "research/tasks/05-retrospective-complexity-assignment/outputs/fork-eips"
TASK07 = ROOT / "research/tasks/07-observed-effort-metrics/outputs/join"
TASK08 = ROOT / "research/tasks/08-hegota-prospective-complexity-assessment/outputs"
ALIGNMENT = ROOT / "research/tasks/05c-amsterdam-human-assessment-alignment/outputs/comparisons"
TIMELINES = ROOT / "research/tasks/04b-fork-evaluation-cutoffs/outputs/review"
VERSION = "1.1.0"
FORK_ORDER = ["shanghai", "cancun", "prague", "osaka", "amsterdam", "hegota"]
FORK_NAMES = {
    "shanghai": "Shanghai / Shapella",
    "cancun": "Cancun / Dencun",
    "prague": "Prague / Pectra",
    "osaka": "Osaka / Fusaka",
    "amsterdam": "Amsterdam / Glamsterdam",
    "hegota": "Hegotá",
}


class BuildError(RuntimeError):
    """Raised when a frozen publication input fails a release invariant."""


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BuildError(f"expected mapping: {path.relative_to(ROOT)}")
    return data


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def source(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}


def retrospective_rows() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    for fork in FORK_ORDER[:-1]:
        for path in sorted((TASK05 / fork).glob("eip-*.yaml")):
            item = load_yaml(path)
            totals = item["totals"]
            under = item["under_specification"]
            rows.append(
                {
                    "assessment_route": f"forks/{fork}/eips/{item['eip']['number']}/",
                    "confidence": item["overall_confidence"],
                    "criteria": [
                        {"id": criterion["id"], "label": criterion["label"], "score": criterion["score"]}
                        for criterion in item["criteria"]
                    ],
                    "eip": item["eip"]["number"],
                    "fork": fork,
                    "layers": item["eip"]["layers"],
                    "mode": "retrospective",
                    "score": totals["primary_score"],
                    "status": "scored",
                    "summary": item["assessment"]["historical_scope_summary"],
                    "tier": totals["complexity_tier"],
                    "title": item["eip"]["title"],
                    "under_specification": under["present"],
                    "under_specification_summary": under["summary"],
                }
            )
            sources.append(source(path))
    return rows, sources


def prospective_rows() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    summary_path = TASK08 / "summary.yaml"
    validation_path = TASK08 / "validation-report.yaml"
    manifest_path = TASK08 / "assessment-manifest.yaml"
    summary = load_yaml(summary_path)
    validation = load_yaml(validation_path)
    manifest = load_yaml(manifest_path)
    expected = {
        "snapshot": "hegota-pfi-2026-08-26-ac450a4",
        "population": 44,
        "scored": 37,
        "not_applicable": 7,
        "total": 776,
    }
    observed = {
        "snapshot": summary["snapshot"]["snapshot_id"],
        "population": summary["population"]["pfi_entries"],
        "scored": summary["population"]["scored_el_rubric"],
        "not_applicable": summary["population"]["not_applicable_total"],
        "total": summary["el_rubric_total"]["score_sum"],
    }
    if observed != expected:
        raise BuildError(f"Task 08 publication gate mismatch: {observed!r}")
    if validation.get("result") != "pass" or manifest.get("assessment_count") != 37:
        raise BuildError("Task 08 validation or assessment freeze is not complete")

    rows: list[dict[str, Any]] = []
    sources = [source(summary_path), source(validation_path), source(manifest_path)]
    for summary_row in summary["scored_eips"]:
        path = TASK08 / "assessments/hegota-pfi-2026-08-26" / f"eip-{summary_row['eip']}.yaml"
        item = load_yaml(path)
        rows.append(
            {
                "assessment_route": f"prospective/hegota/#eip-{item['eip']['number']}",
                "confidence": item["overall_confidence"],
                "criteria": [
                    {"id": criterion["id"], "label": criterion["label"], "score": criterion["score"]}
                    for criterion in item["criteria"]
                ],
                "eip": item["eip"]["number"],
                "fork": "hegota",
                "layers": item["eip"]["layers"],
                "mode": "prospective",
                "score": item["totals"]["primary_score"],
                "status": "scored",
                "summary": item["assessment"]["snapshot_scope_summary"],
                "tier": item["totals"]["complexity_tier"],
                "title": item["eip"]["title"],
                "under_specification": item["under_specification"]["present"],
                "under_specification_summary": item["under_specification"]["summary"],
            }
        )
        sources.append(source(path))
    for item in summary["not_applicable_eips"]:
        rows.append(
            {
                "assessment_route": f"prospective/hegota/#eip-{item['eip']}",
                "confidence": None,
                "criteria": [],
                "eip": item["eip"],
                "exclusion_kind": item["exclusion_kind"],
                "fork": "hegota",
                "layers": item["affected_layers"],
                "mode": "prospective",
                "rationale": item["rationale"],
                "score": None,
                "status": "not_applicable",
                "summary": item["rationale"],
                "tier": None,
                "title": item["title"],
                "under_specification": None,
                "under_specification_summary": None,
            }
        )
    public_summary = {
        "caveats": summary["caveats"],
        "captured_on": summary["snapshot"]["captured_on"],
        "confidence_distribution": summary["distributions"]["confidence"],
        "information_cutoff_at": summary["snapshot"]["information_cutoff_at"],
        "not_applicable": 7,
        "score_sum": 776,
        "scored": 37,
        "snapshot_id": expected["snapshot"],
        "tier_distribution": summary["distributions"]["tiers"],
        "total_entries": 44,
        "under_specification_distribution": summary["distributions"]["under_specification"],
    }
    return rows, public_summary, sources


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def number(value: str | None) -> float | int | None:
    if value in {None, ""}:
        return None
    parsed = float(value)
    return int(parsed) if parsed.is_integer() else parsed


def charts(assessment_rows: list[dict[str, Any]]) -> tuple[dict[str, str], list[dict[str, str]]]:
    chart_dir = PUBLIC / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    sources: list[dict[str, str]] = []
    outputs: dict[str, str] = {}
    historical = [row for row in assessment_rows if row["mode"] == "retrospective"]
    totals = [
        {
            "eips": sum(row["fork"] == fork for row in historical),
            "fork": fork,
            "fork_name": FORK_NAMES[fork],
            "score": sum(row["score"] for row in historical if row["fork"] == fork),
        }
        for fork in FORK_ORDER[:-1]
    ]
    specs: dict[str, dict[str, Any]] = {
        "fork-totals": {
            "data": {"values": totals},
            "description": "Retrospective EL-rubric score sums for five historical fork cohorts.",
            "encoding": {
                "color": {"field": "fork_name", "legend": None, "type": "nominal"},
                "tooltip": [
                    {"field": "fork_name", "title": "Fork", "type": "nominal"},
                    {"field": "score", "title": "Score sum", "type": "quantitative"},
                    {"field": "eips", "title": "Scored EIPs", "type": "quantitative"},
                ],
                "x": {"field": "fork_name", "sort": None, "title": None, "type": "nominal"},
                "y": {"field": "score", "title": "Retrospective score sum", "type": "quantitative"},
            },
            "height": 320,
            "mark": {"cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4, "type": "bar"},
            "title": "Retrospective predicted-complexity totals",
            "width": 760,
        },
        "hegota-scores": {
            "data": {"values": [
                {"eip": f"EIP-{row['eip']}", "score": row["score"], "tier": row["tier"], "under": row["under_specification"]}
                for row in assessment_rows if row["fork"] == "hegota" and row["status"] == "scored"
            ]},
            "description": "Hegotá prospective execution-layer rubric scores, sorted by score.",
            "encoding": {
                "color": {"field": "tier", "scale": {"domain": ["low", "medium", "high"], "range": ["#2f855a", "#b7791f", "#c53030"]}, "title": "Tier", "type": "nominal"},
                "tooltip": [
                    {"field": "eip", "title": "Proposal", "type": "nominal"},
                    {"field": "score", "title": "Score", "type": "quantitative"},
                    {"field": "tier", "title": "Tier", "type": "nominal"},
                    {"field": "under", "title": "Under-specified", "type": "nominal"},
                ],
                "x": {"field": "score", "title": "EL-rubric score", "type": "quantitative"},
                "y": {"field": "eip", "sort": "-x", "title": None, "type": "nominal"},
            },
            "height": 760,
            "mark": {"type": "bar"},
            "title": "Hegotá PFI prospective assessment scores",
            "width": 900,
        },
    }

    joined_path = TASK07 / "predicted-vs-observed.csv"
    joined = read_csv(joined_path)
    sources.append(source(joined_path))
    metrics = [
        ("subst_revisions_after_cutoff", "Specification rework"),
        ("devnet_count", "Integration exposure"),
        ("deps_final", "Coordination surface"),
        ("deps_after_cutoff", "Emergent coupling"),
        ("observed_effort_composite_v0", "Observed-effort composite v0"),
    ]
    values = []
    for row in joined:
        for field, label in metrics:
            value = number(row[field])
            if value is not None:
                values.append({
                    "censored": row["censored"] == "True",
                    "eip": f"EIP-{row['eip']}",
                    "fork": FORK_NAMES[row["fork"]],
                    "metric": label,
                    "observed": value,
                    "predicted": number(row["predicted_score"]),
                })
    specs["predicted-observed"] = {
        "data": {"values": values},
        "description": "Predicted complexity against five score-blind observed-effort proxies for 49 retrospective relationships.",
        "encoding": {
            "color": {"field": "fork", "title": "Fork", "type": "nominal"},
            "column": {"field": "metric", "header": {"labelAngle": 0}, "title": None, "type": "nominal"},
            "shape": {"field": "censored", "scale": {"domain": [False, True], "range": ["circle", "circle"]}, "title": "Right-censored", "type": "nominal"},
            "strokeDash": {"field": "censored", "legend": None, "type": "nominal"},
            "tooltip": [
                {"field": "fork", "title": "Fork", "type": "nominal"},
                {"field": "eip", "title": "EIP", "type": "nominal"},
                {"field": "predicted", "title": "Predicted score", "type": "quantitative"},
                {"field": "observed", "title": "Observed proxy", "type": "quantitative"},
                {"field": "censored", "title": "Right-censored", "type": "nominal"},
            ],
            "x": {"field": "predicted", "title": "Predicted complexity", "type": "quantitative"},
            "y": {"field": "observed", "title": "Observed proxy", "type": "quantitative"},
        },
        "height": 240,
        "mark": {"filled": True, "opacity": 0.82, "size": 70, "type": "point"},
        "title": "Predicted complexity and observed-effort proxies",
        "width": 220,
    }

    alignment_values = []
    for path in sorted(ALIGNMENT.glob("eip-*.yaml")):
        item = load_yaml(path)
        alignment_values.append({
            "automated": item["observations"]["B_historical_rubric_automated"]["total"],
            "clean": item["clean_comparison"]["eligible"],
            "eip": f"EIP-{item['eip']['number']}",
            "human": item["observations"]["C_historical_human"]["recomputed_total"],
        })
        sources.append(source(path))
    specs["human-alignment"] = {
        "data": {"values": alignment_values},
        "description": "Historical-rubric automated and human Amsterdam scores for the 12 reconstructable comparisons.",
        "encoding": {
            "color": {"field": "clean", "title": "Clean comparison", "type": "nominal"},
            "tooltip": [
                {"field": "eip", "title": "EIP", "type": "nominal"},
                {"field": "human", "title": "Human", "type": "quantitative"},
                {"field": "automated", "title": "Automated", "type": "quantitative"},
                {"field": "clean", "title": "Clean", "type": "nominal"},
            ],
            "x": {"field": "human", "scale": {"zero": True}, "title": "Historical human score", "type": "quantitative"},
            "y": {"field": "automated", "scale": {"zero": True}, "title": "Blinded automated score", "type": "quantitative"},
        },
        "height": 380,
        "mark": {"filled": True, "size": 100, "type": "point"},
        "title": "Amsterdam historical-checklist alignment",
        "width": 680,
    }

    for fork in FORK_ORDER[:-1]:
        path = TIMELINES / fork / "el-evaluation-cutoff-review.vl.json"
        spec = json.loads(path.read_text(encoding="utf-8"))
        spec.pop("$schema", None)
        specs[f"timeline-{fork}"] = spec
        sources.append(source(path))

    for name, spec in specs.items():
        path = chart_dir / f"{name}.json"
        write_json(path, spec)
        outputs[name] = f"generated/charts/{name}.json"
    return outputs, sources


def write_csv(rows: list[dict[str, Any]]) -> None:
    fields = ["mode", "fork", "eip", "title", "layers", "status", "score", "tier", "confidence", "under_specification", "exclusion_kind", "rationale"]
    path = PUBLIC / "downloads/complexity-assessments.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({
                **{field: row.get(field) for field in fields},
                "layers": ";".join(row["layers"]),
            })


def build() -> dict[str, Any]:
    retrospective, retrospective_sources = retrospective_rows()
    prospective, hegota, prospective_sources = prospective_rows()
    rows = retrospective + prospective
    rows.sort(key=lambda row: (FORK_ORDER.index(row["fork"]), row["eip"]))
    if len(rows) != 93 or len(retrospective) != 49 or len(prospective) != 44:
        raise BuildError("assessment population mismatch")
    chart_paths, chart_sources = charts(rows)
    write_csv(rows)
    fork_summaries = []
    for fork in FORK_ORDER:
        fork_rows = [row for row in rows if row["fork"] == fork]
        scored = [row for row in fork_rows if row["status"] == "scored"]
        fork_summaries.append({
            "eip_count": len(fork_rows),
            "fork": fork,
            "mode": "prospective" if fork == "hegota" else "retrospective",
            "name": FORK_NAMES[fork],
            "not_applicable_count": len(fork_rows) - len(scored),
            "score_sum": sum(row["score"] for row in scored),
            "scored_count": len(scored),
        })
    unique_eips: dict[int, dict[str, Any]] = {}
    for row in rows:
        item = unique_eips.setdefault(row["eip"], {"eip": row["eip"], "relationships": [], "title": row["title"]})
        item["relationships"].append({"fork": row["fork"], "mode": row["mode"], "score": row["score"], "status": row["status"], "tier": row["tier"]})
    payload = {
        "assessments": rows,
        "charts": chart_paths,
        "eips": [unique_eips[key] for key in sorted(unique_eips)],
        "forks": fork_summaries,
        "hegota": hegota,
        "release_state": "local_preview",
        "schema_version": VERSION,
    }
    write_json(PUBLIC / "publication.json", payload)
    all_sources = retrospective_sources + prospective_sources + chart_sources
    all_sources.sort(key=lambda item: item["path"])
    manifest = {
        "generated_files": [],
        "schema_version": VERSION,
        "source_records": all_sources,
    }
    for path in sorted(PUBLIC.rglob("*")):
        if path.is_file() and path.name != "provenance.json":
            manifest["generated_files"].append({"path": path.relative_to(PUBLIC).as_posix(), "sha256": digest(path)})
    write_json(PUBLIC / "provenance.json", manifest)
    return {"assessments": len(rows), "retrospective": len(retrospective), "prospective": len(prospective), "sources": len(all_sources)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Build twice and require byte-identical output")
    args = parser.parse_args()
    result = build()
    if args.check:
        before = {path.relative_to(PUBLIC): digest(path) for path in PUBLIC.rglob("*") if path.is_file()}
        build()
        after = {path.relative_to(PUBLIC): digest(path) for path in PUBLIC.rglob("*") if path.is_file()}
        if before != after:
            raise BuildError("publication adapter output is not deterministic")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
