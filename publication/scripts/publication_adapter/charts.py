"""Vega-Lite chart specifications (moved from the original single-file adapter)."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import (
    FORK_NAMES,
    FORK_ORDER,
    MULTI_EL_FIRST_DEVNET,
    PROJECTED_MAINNET,
    PUBLIC,
    TASK03_INPUTS as TIMELINE_INPUTS,
    TASK04B_TIMELINES as TIMELINES,
    TASK05C,
    TASK07_JOIN as TASK07,
    load_yaml,
    source,
    write_json,
)

ALIGNMENT = TASK05C / "outputs/comparisons"


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
        at_cutoff_rows = [row for row in fork_rows if row["scope_timing"] == "included_at_cutoff"]
        late_rows = [row for row in fork_rows if row["scope_timing"] == "added_after_cutoff"]
        eips = {row["eip"] for row in at_cutoff_rows}
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
        high_rows = [row for row in at_cutoff_rows if row["tier"] == "high"]
        hardest = max(at_cutoff_rows, key=lambda row: row["score"])
        rows.append(
            {
                "at_cutoff_eips": len(at_cutoff_rows),
                "first_multi_el_devnet": start_id,
                "first_multi_el_devnet_at": start_at.date().isoformat(),
                "fork": fork,
                "fork_name": FORK_NAMES[fork],
                "fork_short": FORK_NAMES[fork].split(" / ")[0],
                "hardest_eip": f"EIP-{hardest['eip']}",
                "high_tier_score_sum": sum(row["score"] for row in high_rows),
                "late_addition_eips": len(late_rows),
                "late_addition_score_sum": sum(row["score"] for row in late_rows),
                "mainnet_at": mainnet_at.date().isoformat(),
                "max_score": hardest["score"],
                "projected": projected,
                "shipping_days": (mainnet_at - start_at).days,
                "total_score": sum(row["score"] for row in at_cutoff_rows),
                "final_scope_score_sum": sum(row["score"] for row in fork_rows),
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
        ("total_score", "Complexity score sum at cutoff"),
        ("high_tier_score_sum", "High-tier score sum at cutoff"),
        ("max_score", "Hardest EIP score at cutoff"),
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
                {"field": "total_score", "title": "Score at cutoff", "type": "quantitative"},
                {"field": "at_cutoff_eips", "title": "EIPs at cutoff", "type": "quantitative"},
                {"field": "late_addition_score_sum", "title": "Added-later score", "type": "quantitative"},
                {"field": "late_addition_eips", "title": "EIPs added later", "type": "quantitative"},
                {"field": "final_scope_score_sum", "title": "Final-scope score", "type": "quantitative"},
                {"field": "high_tier_score_sum", "title": "High-tier sum at cutoff", "type": "quantitative"},
                {"field": "max_score", "title": "Hardest EIP score at cutoff", "type": "quantitative"},
                {"field": "hardest_eip", "title": "Hardest EIP at cutoff", "type": "nominal"},
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
    scopes = [
        ("included_at_cutoff", "Included by cutoff", 0),
        ("added_after_cutoff", "Added after cutoff", 1),
    ]
    totals = []
    for fork in FORK_ORDER[:-1]:
        for scope_timing, scope_label, scope_order in scopes:
            scoped = [
                row
                for row in historical
                if row["fork"] == fork and row["scope_timing"] == scope_timing
            ]
            totals.append(
                {
                    "eips": len(scoped),
                    "fork": fork,
                    "fork_name": FORK_NAMES[fork],
                    "scope": scope_label,
                    "scope_order": scope_order,
                    "score": sum(row["score"] for row in scoped),
                }
            )
    specs: dict[str, dict[str, Any]] = {
        "fork-totals": {
            "data": {"values": totals},
            "description": "Predicted EL-rubric score sums split between EIPs included by each fork's evaluation cutoff and EIPs added later.",
            "height": 320,
            "layer": [
                {
                    "encoding": {
                        "color": {
                            "field": "scope",
                            "legend": {"orient": "top", "title": "Scope timing"},
                            "scale": {
                                "domain": ["Included by cutoff", "Added after cutoff"],
                                "range": ["#3457d5", "#e67e22"],
                            },
                            "type": "nominal",
                        },
                        "order": {"field": "scope_order", "sort": "ascending", "type": "quantitative"},
                        "tooltip": [
                            {"field": "fork_name", "title": "Fork", "type": "nominal"},
                            {"field": "scope", "title": "Scope timing", "type": "nominal"},
                            {"field": "score", "title": "Score subtotal", "type": "quantitative"},
                            {"field": "eips", "title": "EIPs", "type": "quantitative"},
                        ],
                        "x": {"field": "fork_name", "sort": None, "title": None, "type": "nominal"},
                        "y": {
                            "field": "score",
                            "stack": "zero",
                            "title": "Predicted complexity score sum",
                            "type": "quantitative",
                        },
                    },
                    "mark": {"stroke": "white", "strokeWidth": 1, "type": "bar"},
                },
                {
                    "encoding": {
                        "text": {"field": "final_score", "type": "quantitative"},
                        "x": {"field": "fork_name", "sort": None, "title": None, "type": "nominal"},
                        "y": {"field": "final_score", "type": "quantitative"},
                    },
                    "mark": {"dy": -8, "fontSize": 12, "fontWeight": "bold", "type": "text"},
                    "transform": [
                        {
                            "aggregate": [{"as": "final_score", "field": "score", "op": "sum"}],
                            "groupby": ["fork_name"],
                        }
                    ],
                },
            ],
            "title": "Predicted Complexity at and After the Scope Cutoff",
            "width": 760,
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
