#!/usr/bin/env python3
"""Build deterministic, sanitized publication records from frozen research data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
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
TIMELINE_INPUTS = ROOT / "research/tasks/03-fork-development-timelines/inputs/forks"
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
PROJECTED_MAINNET = {"amsterdam": "2026-12-15"}
MULTI_EL_FIRST_DEVNET = {"cancun": "dencun-devnet-4"}


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


def github_current_revision(path: str) -> str:
    return f"https://github.com/ethereum/EIPs/blob/master/{path}"


def github_revision_history(path: str) -> str:
    return f"https://github.com/ethereum/EIPs/commits/master/{path}"


def retrospective_rows() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    for fork in FORK_ORDER[:-1]:
        for path in sorted((TASK05 / fork).glob("eip-*.yaml")):
            item = load_yaml(path)
            totals = item["totals"]
            under = item["under_specification"]
            historical_eip = item["provenance"]["historical_eip"]
            rows.append(
                {
                    "assessment_route": f"forks/{fork}/eips/{item['eip']['number']}/",
                    "assessed_revision": historical_eip["commit"],
                    "assessed_revision_at": historical_eip["committed_at"],
                    "assessed_revision_url": historical_eip["immutable_url"],
                    "confidence": item["overall_confidence"],
                    "criteria": [
                        {"id": criterion["id"], "label": criterion["label"], "score": criterion["score"]}
                        for criterion in item["criteria"]
                    ],
                    "eip": item["eip"]["number"],
                    "fork": fork,
                    "current_revision_url": github_current_revision(historical_eip["path"]),
                    "layers": item["eip"]["layers"],
                    "mode": "retrospective",
                    "score": totals["primary_score"],
                    "status": "scored",
                    "summary": item["assessment"]["historical_scope_summary"],
                    "tier": totals["complexity_tier"],
                    "title": item["eip"]["title"],
                    "revision_history_url": github_revision_history(historical_eip["path"]),
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


def parse_datetime(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def fork_shipping(
    assessment_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    historical = [row for row in assessment_rows if row["mode"] == "retrospective"]
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, str]] = []
    for fork in FORK_ORDER[:-1]:
        path = TIMELINE_INPUTS / f"{fork}.yaml"
        timeline = load_yaml(path)
        sources.append(source(path))
        fork_rows = [row for row in historical if row["fork"] == fork]
        eips = {row["eip"] for row in fork_rows}
        actual_mainnet = next(
            (item["occurred_at"] for item in timeline["milestones"] if item.get("kind") == "mainnet"),
            None,
        )
        projected = actual_mainnet is None
        mainnet_at = parse_datetime(actual_mainnet or PROJECTED_MAINNET[fork])
        _first_el_at, first_el_id = min(
            (parse_datetime(devnet["occurred_at"]), devnet["id"])
            for devnet in timeline["devnets"]
            if eips & set(devnet.get("participation") or [])
        )
        start_id = MULTI_EL_FIRST_DEVNET.get(fork, first_el_id)
        start_at = next(
            parse_datetime(devnet["occurred_at"])
            for devnet in timeline["devnets"]
            if devnet["id"] == start_id
        )
        high_rows = [row for row in fork_rows if row["tier"] == "high"]
        hardest = max(fork_rows, key=lambda row: row["score"])
        rows.append(
            {
                "first_multi_el_devnet": start_id,
                "first_multi_el_devnet_at": start_at.date().isoformat(),
                "fork": fork,
                "fork_name": FORK_NAMES[fork],
                "fork_short": FORK_NAMES[fork].split(" / ")[0],
                "hardest_eip": f"EIP-{hardest['eip']}",
                "high_tier_score_sum": sum(row["score"] for row in high_rows),
                "mainnet_at": mainnet_at.date().isoformat(),
                "max_score": hardest["score"],
                "projected": projected,
                "shipping_days": (mainnet_at - start_at).days,
                "total_score": sum(row["score"] for row in fork_rows),
            }
        )

    return {
        "definition": "Calendar days from the fork's first devnet running at least two independent EL implementations to mainnet activation.",
        "rows": rows,
    }, sources


def fork_shipping_specs(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    colors = ["#3457d5", "#c53030", "#2f855a", "#b7791f", "#7c3aed"]
    domains = [row["fork_name"] for row in analysis["rows"]]
    specs = []
    for field, x_title in [
        ("total_score", "Summed predicted complexity"),
        ("high_tier_score_sum", "High-tier score sum"),
        ("max_score", "Hardest single EIP"),
    ]:
        shared_encoding = {
            "color": {
                "field": "fork_name",
                "legend": None,
                "scale": {"domain": domains, "range": colors},
                "type": "nominal",
            },
            "tooltip": [
                {"field": "fork_name", "title": "Fork", "type": "nominal"},
                {"field": "total_score", "title": "Summed score", "type": "quantitative"},
                {"field": "high_tier_score_sum", "title": "High-tier sum", "type": "quantitative"},
                {"field": "max_score", "title": "Hardest EIP score", "type": "quantitative"},
                {"field": "hardest_eip", "title": "Hardest EIP", "type": "nominal"},
                {"field": "shipping_days", "title": "Shipping span (days)", "type": "quantitative"},
                {"field": "first_multi_el_devnet", "title": "First ≥2-EL devnet", "type": "nominal"},
                {"field": "first_multi_el_devnet_at", "title": "Development start", "type": "temporal"},
                {"field": "mainnet_at", "title": "Mainnet", "type": "temporal"},
                {"field": "projected", "title": "Projected", "type": "nominal"},
            ],
            "x": {"field": field, "scale": {"zero": True}, "title": x_title, "type": "quantitative"},
            "y": {
                "field": "shipping_days",
                "scale": {"zero": True},
                "title": "Days: first ≥2-EL devnet → mainnet",
                "type": "quantitative",
            },
        }
        specs.append(
            {
                "data": {"values": analysis["rows"]},
                "description": f"Fork-level shipping span plotted against {x_title.lower()}.",
                "height": 500,
                "layer": [
                    {
                        "encoding": shared_encoding,
                        "mark": {"filled": True, "size": 130, "stroke": "white", "strokeWidth": 1, "type": "point"},
                        "transform": [{"filter": "datum.projected === false"}],
                    },
                    {
                        "encoding": shared_encoding,
                        "mark": {"filled": False, "size": 150, "strokeWidth": 2.5, "type": "point"},
                        "transform": [{"filter": "datum.projected === true"}],
                    },
                    {
                        "encoding": {
                            "text": {"field": "fork_short", "type": "nominal"},
                            "x": shared_encoding["x"],
                            "y": shared_encoding["y"],
                        },
                        "mark": {"align": "left", "dx": 8, "fontSize": 11, "type": "text"},
                    },
                ],
                "title": x_title,
                "width": 500,
            }
        )
    return specs


def publication_timelines(
    spec: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    schema = spec["$schema"]
    config = spec["config"]
    milestones, histories = spec["vconcat"]
    milestones["width"] = 1080
    milestones["height"] = min(milestones["height"], 320)
    milestones.pop("title", None)

    histories.pop("title", None)
    histories["facet"]["row"]["header"]["labelFontSize"] = 10
    histories["facet"]["row"]["header"]["labelLimit"] = 245
    histories["spec"]["width"] = 820

    for value in histories["data"]["values"]:
        if "cohort" in value:
            value["scope_at_cutoff"] = value.pop("cohort")
        if value.get("selection_mode") == "aggregation_cohort":
            value["selection_mode"] = "fork scope"

    for item in histories["spec"]["layer"]:
        encoding = item.get("encoding", {})
        if "x" in encoding:
            encoding["x"]["axis"] = {
                "domain": True,
                "format": "%b %Y",
                "grid": True,
                "gridColor": "#E2E8F0",
                "labelAngle": 0,
                "labelColor": "#475569",
                "labels": True,
                "orient": "top",
                "tickCount": 8,
                "ticks": True,
                "title": None,
            }
        if "tooltip" in encoding:
            tooltip = []
            for field in encoding["tooltip"]:
                if field.get("field") == "rationale":
                    continue
                if field.get("field") == "cohort":
                    field["field"] = "scope_at_cutoff"
                    field["title"] = "Scope at cutoff"
                tooltip.append(field)
            encoding["tooltip"] = tooltip
    common = {"$schema": schema, "config": config}
    return ({**common, **milestones}, {**common, **histories})


def charts(
    assessment_rows: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, Any], list[dict[str, Any]], list[dict[str, str]]]:
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
            "description": "Retrospective EL-rubric score sums for five historical forks.",
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
        (
            "subst_revisions_after_cutoff",
            "Specification rework",
            "predicted-observed-specification-rework",
            "Predicted Complexity Versus Specification Rework",
        ),
        (
            "deps_after_cutoff",
            "New EIP interactions",
            "predicted-observed-eip-interactions",
            "Predicted Complexity Versus New EIP Interactions",
        ),
    ]
    for field, label, chart_id, chart_title in metrics:
        values = []
        for row in joined:
            if row["censored"] == "True":
                continue
            value = number(row[field])
            if value is not None:
                values.append({
                    "eip": f"EIP-{row['eip']}",
                    "fork": FORK_NAMES[row["fork"]],
                    "metric": label,
                    "observed": value,
                    "predicted": number(row["predicted_score"]),
                })
        specs[chart_id] = {
            "data": {"values": values},
            "description": f"Predicted complexity against the score-blind {label.lower()} proxy for 34 relationships in shipped forks.",
            "encoding": {
                "color": {
                    "field": "fork",
                    "legend": {"orient": "bottom"},
                    "title": "Fork",
                    "type": "nominal",
                },
                "tooltip": [
                    {"field": "fork", "title": "Fork", "type": "nominal"},
                    {"field": "eip", "title": "EIP", "type": "nominal"},
                    {"field": "predicted", "title": "Predicted score", "type": "quantitative"},
                    {"field": "observed", "title": label, "type": "quantitative"},
                ],
                "x": {"field": "predicted", "title": "Predicted complexity", "type": "quantitative"},
                "y": {"field": "observed", "title": label, "type": "quantitative"},
            },
            "height": 500,
            "mark": {"filled": True, "opacity": 0.82, "size": 70, "type": "point"},
            "title": chart_title,
            "width": 500,
        }

    shipping_analysis, shipping_sources = fork_shipping(assessment_rows)
    shipping_specs = fork_shipping_specs(shipping_analysis)
    specs["fork-shipping"] = shipping_specs[0]
    specs["fork-shipping-high-tier"] = shipping_specs[1]
    specs["fork-shipping-hardest-eip"] = shipping_specs[2]
    sources.extend(shipping_sources)

    alignment_rows = []
    for path in sorted(ALIGNMENT.glob("eip-*.yaml")):
        item = load_yaml(path)
        observations = item["observations"]
        alignment_rows.append(
            {
                "clean": item["clean_comparison"]["eligible"],
                "eip": item["eip"]["number"],
                "human_score": observations["C_historical_human"]["recomputed_total"],
                "human_tier": observations["C_historical_human"]["recomputed_tier"],
                "llm_v1_score": observations["B_historical_rubric_automated"]["total"],
                "llm_v1_tier": observations["B_historical_rubric_automated"]["tier"],
                "llm_v2_score": observations["A_current_rubric_automated"]["total"],
                "llm_v2_tier": observations["A_current_rubric_automated"]["tier"],
                "title": item["eip"]["title"],
            }
        )
        sources.append(source(path))
    alignment_rows.sort(key=lambda row: (-row["human_score"], row["eip"]))
    eip_order = [f"EIP-{row['eip']}" for row in alignment_rows]
    alignment_values = []
    for row in alignment_rows:
        for evaluation, score, tier in [
            ("Human · v1 rubric", row["human_score"], row["human_tier"]),
            ("LLM · v1 rubric", row["llm_v1_score"], row["llm_v1_tier"]),
            ("LLM · v2 rubric", row["llm_v2_score"], row["llm_v2_tier"]),
        ]:
            alignment_values.append(
                {
                    "clean": row["clean"],
                    "eip": f"EIP-{row['eip']}",
                    "evaluation": evaluation,
                    "score": score,
                    "tier": tier,
                    "title": row["title"],
                }
            )
    specs["human-alignment"] = {
        "data": {"values": alignment_values},
        "description": "Three complexity-evaluation scores for each of 12 Amsterdam EIPs, ordered by the historical human score.",
        "height": 460,
        "layer": [
            {
                "encoding": {
                    "x": {"aggregate": "min", "field": "score", "type": "quantitative"},
                    "x2": {"aggregate": "max", "field": "score"},
                    "y": {"field": "eip", "sort": eip_order, "title": None, "type": "nominal"},
                },
                "mark": {"color": "#d9d7cf", "strokeWidth": 2, "type": "rule"},
            },
            {
                "encoding": {
                    "color": {
                        "field": "evaluation",
                        "legend": {"orient": "top", "title": None},
                        "scale": {
                            "domain": ["Human · v1 rubric", "LLM · v1 rubric", "LLM · v2 rubric"],
                            "range": ["#17202a", "#3457d5", "#b52e31"],
                        },
                        "type": "nominal",
                    },
                    "shape": {"field": "evaluation", "legend": None, "type": "nominal"},
                    "tooltip": [
                        {"field": "eip", "title": "EIP", "type": "nominal"},
                        {"field": "title", "title": "Title", "type": "nominal"},
                        {"field": "evaluation", "title": "Evaluation", "type": "nominal"},
                        {"field": "score", "title": "Score", "type": "quantitative"},
                        {"field": "tier", "title": "Tier", "type": "nominal"},
                        {"field": "clean", "title": "Clean same-rubric comparison", "type": "nominal"},
                    ],
                    "x": {
                        "field": "score",
                        "scale": {"domain": [0, 42]},
                        "title": "Complexity score (rubric-specific scale)",
                        "type": "quantitative",
                    },
                    "y": {"field": "eip", "sort": eip_order, "title": None, "type": "nominal"},
                },
                "mark": {"filled": True, "size": 120, "stroke": "white", "strokeWidth": 1, "type": "point"},
            },
        ],
        "title": {
            "subtitle": "V2 uses a different rubric; compare ordering rather than raw distance.",
            "text": "Amsterdam Human and Blinded LLM Scores",
        },
        "width": 680,
    }

    for fork in FORK_ORDER[:-1]:
        path = TIMELINES / fork / "el-evaluation-cutoff-review.vl.json"
        spec = json.loads(path.read_text(encoding="utf-8"))
        milestones, histories = publication_timelines(spec)
        specs[f"fork-milestones-{fork}"] = milestones
        specs[f"timeline-{fork}"] = histories
        sources.append(source(path))

    for name, spec in specs.items():
        path = chart_dir / f"{name}.json"
        write_json(path, spec)
        outputs[name] = f"generated/charts/{name}.json"
    return outputs, shipping_analysis, alignment_rows, sources


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
    chart_paths, shipping_analysis, alignment_rows, chart_sources = charts(rows)
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
        "fork_shipping": shipping_analysis,
        "forks": fork_summaries,
        "hegota": hegota,
        "human_llm": {"rows": alignment_rows},
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
