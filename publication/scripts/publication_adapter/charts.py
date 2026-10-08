"""Vega-Lite chart specifications (moved from the original single-file adapter)."""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import (
    EVALUATIONS,
    FORK_NAMES,
    FORK_ORDER,
    MULTI_EL_FIRST_DEVNET,
    PROJECTED_MAINNET,
    PUBLIC,
    TASK03_INPUTS as TIMELINE_INPUTS,
    TASK04B_TIMELINES as TIMELINES,
    TASK07_JOIN as TASK07,
    load_yaml,
    source,
    write_json,
)



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


# Two-sided 95% Student t quantile for n - 2 = 3 degrees of freedom (five forks).
T_975 = {3: 3.182446305284263}
BAND_STEPS = 60


def least_squares(rows: list[dict[str, Any]], x_max: float) -> dict[str, Any]:
    """Ordinary least squares of shipping days on at-cutoff score, with a 95% prediction band."""
    xs = [row["total_score"] for row in rows]
    ys = [row["shipping_days"] for row in rows]
    n = len(xs)
    if n - 2 not in T_975:
        raise ValueError(f"no t quantile for {n} points")
    x_mean, y_mean = sum(xs) / n, sum(ys) / n
    sxx = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / sxx
    intercept = y_mean - slope * x_mean
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    se = math.sqrt(sum(item**2 for item in residuals) / (n - 2))
    ss_total = sum((y - y_mean) ** 2 for y in ys)
    t = T_975[n - 2]
    band = []
    for step in range(BAND_STEPS + 1):
        x = x_max * step / BAND_STEPS
        fitted = intercept + slope * x
        half = t * se * math.sqrt(1 + 1 / n + (x - x_mean) ** 2 / sxx)
        band.append({"x": round(x, 2), "fit": round(fitted, 2), "lower": round(fitted - half, 2), "upper": round(fitted + half, 2)})
    return {
        "method": "Ordinary least squares over the five forks; band is the 95% prediction interval for one new fork (t, 3 degrees of freedom).",
        "n": n,
        "slope_days_per_point": round(slope, 4),
        "intercept_days": round(intercept, 2),
        "residual_standard_error_days": round(se, 2),
        "r_squared": round(1 - sum(item**2 for item in residuals) / ss_total, 3),
        "band": band,
    }


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
        band_layers = []
        if field == "total_score" and analysis.get("fit"):
            band_x = {"field": "x", "type": "quantitative", "title": x_title, "scale": {"zero": True}}
            band_y = {"field": "lower", "type": "quantitative", "title": "Days: first ≥2-EL devnet → mainnet", "scale": {"zero": True}}
            band_layers = [
                {
                    "data": {"values": analysis["fit"]["band"]},
                    "transform": [{"calculate": "max(0, datum.lower)", "as": "lower"}],
                    "encoding": {"x": band_x, "y": band_y, "y2": {"field": "upper"}},
                    "mark": {"type": "area", "color": "#94a3b8", "opacity": 0.22},
                },
                {
                    "data": {"values": analysis["fit"]["band"]},
                    "encoding": {"x": band_x, "y": {**band_y, "field": "fit"}},
                    "mark": {"type": "line", "color": "#64748b", "strokeDash": [6, 4], "strokeWidth": 1.5},
                },
            ]
        specs.append(
            {
                "data": {"values": analysis["rows"]},
                "description": f"Fork-level shipping span plotted against {x_title.lower()}.",
                "height": 500,
                "layer": [
                    *band_layers,
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
    evaluation_rows: dict[str, list[dict[str, Any]]],
    primary: str,
    x_extent: float,
) -> tuple[dict[str, str], dict[str, Any], list[dict[str, str]]]:
    chart_dir = PUBLIC / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    sources: list[dict[str, str]] = []
    outputs: dict[str, str] = {}
    historical = [row for row in assessment_rows if row["mode"] == "retrospective"]
    specs: dict[str, dict[str, Any]] = {}

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

    by_evaluation = {}
    shipping_sources: list[dict[str, str]] = []
    for key, rows in evaluation_rows.items():
        analysis, shipping_sources = fork_shipping(rows)
        by_evaluation[key] = analysis
    x_max = max(x_extent, *[row["total_score"] for item in by_evaluation.values() for row in item["rows"]]) * 1.1
    x_max = math.ceil(x_max / 50) * 50
    for key, analysis in by_evaluation.items():
        analysis["fit"] = least_squares(analysis["rows"], x_max)
        analysis["evaluation"] = key
        analysis["label"] = EVALUATIONS[key]["label"]
        analysis["rubric_revision"] = EVALUATIONS[key]["revision"]
    shipping_analysis = {**by_evaluation[primary], "x_max": x_max, "primary_evaluation": primary, "evaluations": by_evaluation}
    shipping_specs = fork_shipping_specs(shipping_analysis)
    specs["fork-shipping"] = shipping_specs[0]
    specs["fork-shipping-high-tier"] = shipping_specs[1]
    specs["fork-shipping-hardest-eip"] = shipping_specs[2]
    sources.extend(shipping_sources)

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
    return outputs, shipping_analysis, sources
