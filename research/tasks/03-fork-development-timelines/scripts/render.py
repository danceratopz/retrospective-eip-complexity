#!/usr/bin/env python3
"""Build reproducible fork, EL, and CL development timelines."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import altair as alt
from cairosvg import surface as cairosvg_surface
import vl_convert as vlc
import yaml


TASK_ID = "03-fork-development-timelines"
TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
INPUT_ROOT = TASK_ROOT / "inputs" / "forks"
OUTPUT_ROOT = TASK_ROOT / "outputs"

LAYER_NAMES = {"execution": "Execution layer", "consensus": "Consensus layer"}
LAYER_SHORT = {"execution": "EL", "consensus": "CL"}
LAYER_COLORS = {"execution": "#2563EB", "consensus": "#7C3AED"}
SERIES_COLORS = {
    "bal": "#0F9D8A",
    "epbs": "#8B5CF6",
    "combined": "#E76F51",
    "network": "#334155",
    "fork": "#64748B",
}
SEMANTIC_COLORS = {
    "substantive": "#111827",
    "non_substantive": "#CBD5E1",
    "uncertain": "#DC2626",
}
INCLUSION_COLORS = {
    "proposed_for_inclusion": "#94A3B8",
    "considered_for_inclusion": "#F59E0B",
    "scheduled_for_inclusion": "#10B981",
    "included": "#047857",
    "removed_from_consideration": "#EF4444",
    "removed_from_schedule": "#B91C1C",
    "declined_for_inclusion": "#991B1B",
    "unknown": "#64748B",
}
INCLUSION_LABELS = {
    "proposed_for_inclusion": "PFI",
    "considered_for_inclusion": "CFI",
    "scheduled_for_inclusion": "SFI",
    "included": "Included",
    "removed_from_consideration": "Removed from CFI",
    "removed_from_schedule": "Removed from SFI",
    "declined_for_inclusion": "Declined",
    "unknown": "Uncertain transition",
}
MILESTONE_COLORS = {
    "fork_definition": "#64748B",
    "testnet": "#0284C7",
    "mainnet": "#DC2626",
    "bpo": "#D97706",
}
ASSESSMENT_MARKER_COLORS = {
    "Selected assessment ref": "#DB2777",
    "Proposal anchor": "#D97706",
}


class InputError(RuntimeError):
    """Raised when a research input violates the plot contract."""


class DeterministicPDFSurface(cairosvg_surface.PDFSurface):
    """CairoSVG PDF surface with stable metadata."""

    def finish(self) -> None:
        fixed_date = "1970-01-01T00:00:00Z"
        self.cairo.set_metadata(
            cairosvg_surface.cairo.PDF_METADATA_CREATE_DATE, fixed_date
        )
        self.cairo.set_metadata(
            cairosvg_surface.cairo.PDF_METADATA_MOD_DATE, fixed_date
        )
        super().finish()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise InputError(f"Expected a YAML mapping: {path}")
    return data


def parse_datetime(value: str) -> datetime:
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), datetime.min.time(), UTC)
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def chart_date(value: str | datetime) -> str:
    parsed = value if isinstance(value, datetime) else parse_datetime(value)
    return parsed.date().isoformat()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8")


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def source_map(path: Path) -> dict[str, dict[str, Any]]:
    sources = load_yaml(path).get("sources", [])
    result: dict[str, dict[str, Any]] = {}
    for source in sources:
        source_id = source.get("id")
        if not source_id or source_id in result:
            raise InputError(f"Missing or duplicate source ID in {path}: {source_id!r}")
        result[source_id] = source
    return result


def source_details(
    source_ids: Iterable[str],
    sources: dict[str, dict[str, Any]],
    *,
    preferred_url: str | None = None,
) -> dict[str, str]:
    ids = list(source_ids)
    missing = [source_id for source_id in ids if source_id not in sources]
    if missing:
        raise InputError(f"Unresolved source IDs: {', '.join(missing)}")
    primary = sources[ids[0]] if ids else {}
    immutable = primary.get("immutable_url") or primary.get("canonical_url") or ""
    return {
        "source_ids": ", ".join(ids),
        "source_title": primary.get("title", "Unknown source"),
        "source_url": preferred_url or immutable,
        "provenance_url": immutable,
    }


def resolve(config_path: Path, value: str) -> Path:
    return (config_path.parent / value).resolve()


def layer_tag(layers: list[str]) -> str:
    if layers == ["execution", "consensus"] or set(layers) == {
        "execution",
        "consensus",
    }:
        return "EL+CL"
    return "+".join(LAYER_SHORT[layer] for layer in layers)


def eip_label(number: int, title: str, layers: list[str] | None = None) -> str:
    prefix = f"[{layer_tag(layers)}] " if layers else ""
    return f"{prefix}EIP-{number} · {title}"


def value_at(events: list[dict[str, Any]], when: datetime, semantic: str | None) -> int:
    return sum(
        1
        for event in events
        if event["parsed_at"] <= when
        and (semantic is None or event["semantic_effect"] == semantic)
    )


def weekly_floor(when: datetime) -> str:
    monday = when.date() - timedelta(days=when.weekday())
    return monday.isoformat()


def load_fork(config_path: Path) -> tuple[dict[str, Any], set[Path]]:
    config = load_yaml(config_path)
    used_files = {config_path}
    if config.get("task_id") != TASK_ID:
        raise InputError(f"Unexpected task_id in {config_path}")

    paths = {
        key: resolve(config_path, config[key])
        for key in (
            "task_01_fork_record",
            "task_01_fork_eips",
            "task_01_eips",
            "task_01_fork_sources",
            "task_01_eip_sources",
            "source_registry",
        )
    }
    required_files = [
        paths["task_01_fork_record"],
        paths["task_01_fork_sources"],
        paths["source_registry"],
    ]
    for path in required_files:
        if not path.is_file():
            raise InputError(f"Missing input: {path}")
        used_files.add(path)

    fork_record = load_yaml(paths["task_01_fork_record"])
    fork_id = config["fork"]["id"]
    if fork_record["fork"]["id"] != fork_id:
        raise InputError(f"Fork ID mismatch for {config_path}")

    task03_sources = source_map(paths["source_registry"])
    task01_fork_sources = source_map(paths["task_01_fork_sources"])
    eips: list[dict[str, Any]] = []

    relationship_paths = sorted(paths["task_01_fork_eips"].glob("eip-*.yaml"))
    if not relationship_paths:
        raise InputError(f"No fork-EIP records found under {paths['task_01_fork_eips']}")

    for relationship_path in relationship_paths:
        relationship = load_yaml(relationship_path)
        number = int(relationship["eip"]["number"])
        eip_path = paths["task_01_eips"] / f"eip-{number}.yaml"
        eip_sources_path = paths["task_01_eip_sources"] / f"eip-{number}.yaml"
        for path in (relationship_path, eip_path, eip_sources_path):
            if not path.is_file():
                raise InputError(f"Missing EIP input: {path}")
            used_files.add(path)
        history = load_yaml(eip_path)
        eip_sources = source_map(eip_sources_path)
        # The numbered EIP record is authoritative for the display title. Task 01
        # fork relationships can retain an older title after an EIP is renamed;
        # identity is already fixed by the numbered relationship and file path.
        title = history["eip"]["title"]

        creation_commit = history["creation"]["first_repository_commit"]
        creation_at = parse_datetime(creation_commit["committed_at"])
        creation_url = (
            f"https://github.com/ethereum/EIPs/commit/{creation_commit['commit']}"
        )
        creation = {
            "eip": number,
            "title": title,
            "occurred_at": creation_commit["committed_at"],
            "date": chart_date(creation_at),
            "frontmatter_date": history["creation"]["frontmatter_date"],
            "commit": creation_commit["commit"],
            "source_url": creation_url,
            "source_ids": creation_commit.get("source_ids", []),
        }

        revisions: list[dict[str, Any]] = []
        history_events = history["revision_history"]["events"]
        for event in history_events:
            if event["event_kind"] == "creation":
                continue
            committed_at = event["committed_at"]
            parsed_at = parse_datetime(committed_at)
            event_source = source_details(event.get("source_ids", []), eip_sources)
            revisions.append(
                {
                    "id": event["id"],
                    "eip": number,
                    "title": title,
                    "occurred_at": committed_at,
                    "date": chart_date(parsed_at),
                    "parsed_at": parsed_at,
                    "commit": event["commit"],
                    "change_type": event["change_type"],
                    "semantic_effect": event["semantic_effect"],
                    "summary": event["summary"],
                    "rationale": event["rationale"],
                    "confidence": event["confidence"],
                    **event_source,
                }
            )
        revisions.sort(key=lambda event: (event["parsed_at"], event["id"]))

        summary = history["revision_history"]["summary"]
        observed_counts = Counter(event["semantic_effect"] for event in revisions)
        expected = {
            "substantive": summary["substantive_revision_count"],
            "non_substantive": summary["non_substantive_revision_count"],
            "uncertain": summary["uncertain_revision_count"],
        }
        if dict(observed_counts) != {key: value for key, value in expected.items() if value}:
            raise InputError(f"Revision summary mismatch for EIP-{number}")

        inclusions: list[dict[str, Any]] = []
        for event in relationship.get("inclusion_history", {}).get("events", []):
            event_source = source_details(
                event.get("source_ids", []), task01_fork_sources
            )
            inclusions.append(
                {
                    "id": event["id"],
                    "eip": number,
                    "title": title,
                    "occurred_at": event["occurred_at"],
                    "date": chart_date(event["occurred_at"]),
                    "raw_label": event["raw_label"],
                    "normalized_state": event["normalized_state"],
                    "normalization_rationale": event["normalization_rationale"],
                    "decision_body": event.get("decision_body") or "Unknown",
                    **event_source,
                }
            )

        eips.append(
            {
                "number": number,
                "title": title,
                "layers": relationship["eip"]["layers"],
                "label": eip_label(number, title),
                "overview_label": eip_label(
                    number, title, relationship["eip"]["layers"]
                ),
                "creation": creation,
                "revisions": revisions,
                "inclusions": inclusions,
                "unknowns": relationship.get("unknowns", []),
            }
        )

    expected_total = fork_record["membership_summary"]["total_eips"]
    if len(eips) != expected_total:
        raise InputError(
            f"{fork_id}: expected {expected_total} EIPs, found {len(eips)}"
        )
    inventory = {eip["number"] for eip in eips}

    milestones: list[dict[str, Any]] = []
    for milestone in config.get("milestones", []):
        details = source_details(milestone["source_ids"], task03_sources)
        milestone_eips = milestone.get("eips")
        if milestone_eips and not set(milestone_eips) <= inventory:
            raise InputError(f"Unknown EIP in milestone {milestone['id']}")
        milestones.append(
            {
                **milestone,
                "date": chart_date(milestone["occurred_at"]),
                **details,
            }
        )

    devnets: list[dict[str, Any]] = []
    devnet_ids: set[str] = set()
    for devnet in config.get("devnets", []):
        if devnet["id"] in devnet_ids:
            raise InputError(f"Duplicate devnet ID: {devnet['id']}")
        devnet_ids.add(devnet["id"])
        explicit = list(devnet.get("participation", []))
        inferred = list(devnet.get("inferred_participation", []))
        inferred_numbers = [int(item["eip"]) for item in inferred]
        participants = explicit + inferred_numbers
        if not set(participants) <= inventory:
            unknown = sorted(set(participants) - inventory)
            raise InputError(f"{devnet['id']} references out-of-fork EIPs: {unknown}")
        details = source_details(
            devnet["source_ids"],
            task03_sources,
            preferred_url=devnet.get("source_url"),
        )
        devnets.append(
            {
                **devnet,
                "date": chart_date(devnet["occurred_at"]),
                "participants": participants,
                **details,
            }
        )

    start = parse_datetime(config["plot"]["start_date"])
    end = parse_datetime(config["plot"]["end_date"])
    if start >= end:
        raise InputError(f"Invalid plot window for {fork_id}")

    dataset = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "fork": config["fork"],
        "plot": config["plot"],
        "eips": eips,
        "milestones": milestones,
        "devnets": devnets,
        "unknowns": config.get("unknowns", []),
    }
    return dataset, used_files


def exportable_dataset(dataset: dict[str, Any]) -> dict[str, Any]:
    """Remove internal datetime helpers before writing plot-data.json."""

    def clean(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat().replace("+00:00", "Z")
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value

    return clean(dataset)


def shared_x(domain: list[str], *, axis: bool) -> alt.X:
    return alt.X(
        "date:T",
        title=None,
        scale=alt.Scale(domain=domain, nice=False),
        axis=(
            alt.Axis(
                format="%b %Y",
                grid=False,
                labelAngle=0,
                labelColor="#475569",
                orient="top",
                tickCount=10,
                title=None,
            )
            if axis
            else alt.Axis(labels=False, ticks=False, domain=False, title=None)
        ),
    )


def event_strip(
    events: list[dict[str, Any]],
    *,
    domain: list[str],
    width: int,
    title: str,
) -> alt.Chart:
    records: list[dict[str, Any]] = []
    for index, event in enumerate(sorted(events, key=lambda item: item["date"])):
        label = event["label"]
        if event.get("status") == "planned":
            label += " · planned"
        series = event.get("series")
        kind = event.get("kind")
        color_key = series or ("network" if kind in {"testnet", "mainnet", "bpo"} else "fork")
        records.append(
            {
                "date": event["date"],
                "occurred_at": event["occurred_at"],
                "event_label": label,
                "event_order": index,
                "event_type": series or kind,
                "status": event.get("status", "actual"),
                "confidence": event.get("confidence", "high"),
                "basis": event.get("participation_basis", kind or "milestone"),
                "source_title": event["source_title"],
                "source_ids": event["source_ids"],
                "source_url": event["source_url"],
                "provenance_url": event["provenance_url"],
                "color": SERIES_COLORS.get(color_key, "#64748B"),
            }
        )
    if not records:
        records = [
            {
                "date": domain[0],
                "occurred_at": domain[0],
                "event_label": "No dated milestones",
                "event_order": 0,
                "event_type": "none",
                "status": "unknown",
                "confidence": "unknown",
                "basis": "none",
                "source_title": "None",
                "source_ids": "",
                "source_url": "",
                "provenance_url": "",
                "color": "#CBD5E1",
            }
        ]
    order = [record["event_label"] for record in reversed(records)]
    base = alt.Chart(alt.Data(values=records)).encode(
        x=shared_x(domain, axis=True),
        y=alt.Y(
            "event_label:N",
            sort=order,
            title=None,
            axis=alt.Axis(
                domain=False,
                ticks=False,
                labelColor="#334155",
                labelLimit=300,
                labelPadding=8,
            ),
        ),
        href=alt.Href("source_url:N"),
        tooltip=[
            alt.Tooltip("event_label:N", title="Event"),
            alt.Tooltip("occurred_at:N", title="Date / time (UTC)"),
            alt.Tooltip("event_type:N", title="Type"),
            alt.Tooltip("status:N", title="Status"),
            alt.Tooltip("confidence:N", title="Confidence"),
            alt.Tooltip("basis:N", title="Evidence basis"),
            alt.Tooltip("source_title:N", title="Pinned source"),
            alt.Tooltip("source_url:N", title="Canonical source"),
            alt.Tooltip("provenance_url:N", title="Immutable provenance"),
        ],
    )
    rules = base.mark_rule(color="#E2E8F0", strokeWidth=1)
    points = base.mark_point(filled=True, size=85, strokeWidth=2).encode(
        color=alt.Color("color:N", scale=None, legend=None),
        shape=alt.Shape(
            "status:N",
            scale=alt.Scale(
                domain=["actual", "planned", "cancelled", "unknown"],
                range=["circle", "diamond", "cross", "square"],
            ),
            legend=None,
        ),
        opacity=alt.condition(alt.datum.status == "planned", alt.value(0.65), alt.value(1)),
    )
    return (rules + points).properties(
        width=width,
        height=max(90, len(records) * 19),
        title=alt.TitleParams(title, anchor="start", color="#0F172A", fontSize=15),
    )


def curve_records(
    eip: dict[str, Any], start: datetime, end: datetime
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    revisions = eip["revisions"]
    creation_at = parse_datetime(eip["creation"]["occurred_at"])
    first_date = start if creation_at < start else creation_at
    for series, semantic in (
        ("All revisions", None),
        ("Substantive revisions", "substantive"),
    ):
        value = value_at(revisions, first_date, semantic)
        records.append(
            {
                "record_type": "curve",
                "date": chart_date(first_date),
                "value": value,
                "series": series,
                "eip": eip["number"],
                "eip_label": eip["label"],
            }
        )
        running = value
        for event in revisions:
            if event["parsed_at"] <= first_date or event["parsed_at"] > end:
                continue
            if semantic is None or event["semantic_effect"] == semantic:
                running += 1
                records.append(
                    {
                        "record_type": "curve",
                        "date": event["date"],
                        "value": running,
                        "series": series,
                        "eip": eip["number"],
                        "eip_label": eip["label"],
                    }
                )
        records.append(
            {
                "record_type": "curve",
                "date": chart_date(end),
                "value": running,
                "series": series,
                "eip": eip["number"],
                "eip_label": eip["label"],
            }
        )
    return records


def layer_panel_records(
    dataset: dict[str, Any], layer: str
) -> tuple[list[dict[str, Any]], list[str]]:
    start = parse_datetime(dataset["plot"]["start_date"])
    end = parse_datetime(dataset["plot"]["end_date"])
    layer_eips = [eip for eip in dataset["eips"] if layer in eip["layers"]]
    labels = [eip["label"] for eip in sorted(layer_eips, key=lambda item: item["number"])]
    records: list[dict[str, Any]] = []

    for eip in layer_eips:
        records.extend(curve_records(eip, start, end))
        revisions = eip["revisions"]
        for event in revisions:
            if not start <= event["parsed_at"] <= end:
                continue
            records.append(
                {
                    "record_type": "commit",
                    "date": event["date"],
                    "value": value_at(revisions, event["parsed_at"], "substantive"),
                    "eip": eip["number"],
                    "eip_label": eip["label"],
                    "occurred_at": event["occurred_at"],
                    "event_label": event["summary"],
                    "event_kind": event["change_type"],
                    "semantic_effect": event["semantic_effect"],
                    "confidence": event["confidence"],
                    "rationale": event["rationale"],
                    "commit": event["commit"],
                    "source_title": event["source_title"],
                    "source_url": event["source_url"],
                }
            )

        creation_at = parse_datetime(eip["creation"]["occurred_at"])
        creation_clipped = creation_at < start
        if creation_at <= end:
            marker_at = start if creation_clipped else creation_at
            records.append(
                {
                    "record_type": "eip_marker",
                    "date": chart_date(marker_at),
                    "value": value_at(revisions, marker_at, "substantive"),
                    "eip": eip["number"],
                    "eip_label": eip["label"],
                    "occurred_at": eip["creation"]["occurred_at"],
                    "event_label": (
                        "Created before displayed window" if creation_clipped else "Created"
                    ),
                    "event_kind": "creation_before_window" if creation_clipped else "creation",
                    "raw_label": f"Frontmatter date: {eip['creation']['frontmatter_date']}",
                    "confidence": "high",
                    "source_title": "EIP creation commit",
                    "source_url": eip["creation"]["source_url"],
                }
            )

        previous_inclusion_state: str | None = None
        inclusion_events = sorted(
            eip["inclusions"],
            key=lambda item: (parse_datetime(item["occurred_at"]), item["id"]),
        )
        for event in inclusion_events:
            event_at = parse_datetime(event["occurred_at"])
            normalized_state = event["normalized_state"]
            if normalized_state == "unknown":
                event_role = "uncertain_record"
                event_role_label = "Uncertain record (transition unknown)"
            elif normalized_state == previous_inclusion_state:
                event_role = "same_state_record"
                event_role_label = "Same-state record (no transition)"
            else:
                event_role = "state_transition"
                event_role_label = "State transition"
                previous_inclusion_state = normalized_state
            if not start <= event_at <= end:
                continue
            event_label = INCLUSION_LABELS.get(
                normalized_state, normalized_state
            )
            if (
                normalized_state == "considered_for_inclusion"
                and "RIP-" in event["raw_label"]
            ):
                event_label = "CFI (RIP)"
            records.append(
                {
                    "record_type": "inclusion_marker",
                    "date": event["date"],
                    "value": value_at(revisions, event_at, "substantive"),
                    "eip": eip["number"],
                    "eip_label": eip["label"],
                    "occurred_at": event["occurred_at"],
                    "event_label": event_label,
                    "event_kind": normalized_state,
                    "event_role": event_role,
                    "event_role_label": event_role_label,
                    "raw_label": event["raw_label"],
                    "confidence": "high" if normalized_state != "unknown" else "uncertain",
                    "rationale": event["normalization_rationale"],
                    "source_title": event["source_title"],
                    "source_url": event["source_url"],
                }
            )

        for devnet in dataset["devnets"]:
            if eip["number"] not in devnet["participants"]:
                continue
            event_at = parse_datetime(devnet["occurred_at"])
            if not start <= event_at <= end:
                continue
            inferred = next(
                (
                    item
                    for item in devnet.get("inferred_participation", [])
                    if int(item["eip"]) == eip["number"]
                ),
                None,
            )
            records.append(
                {
                    "record_type": "devnet_marker",
                    "date": devnet["date"],
                    "value": 0,
                    "eip": eip["number"],
                    "eip_label": eip["label"],
                    "occurred_at": devnet["occurred_at"],
                    "event_label": devnet["id"],
                    "event_kind": devnet["series"],
                    "status": devnet["status"],
                    "confidence": inferred["confidence"] if inferred else devnet["confidence"],
                    "rationale": (
                        inferred["note"]
                        if inferred
                        else f"Participation basis: {devnet['participation_basis']}"
                    ),
                    "source_title": devnet["source_title"],
                    "source_url": devnet["source_url"],
                    "provenance_url": devnet["provenance_url"],
                }
            )

        for milestone in dataset["milestones"]:
            if layer not in milestone["layers"] or milestone["kind"] == "fork_definition":
                continue
            milestone_eips = milestone.get("eips")
            if milestone_eips and eip["number"] not in milestone_eips:
                continue
            event_at = parse_datetime(milestone["occurred_at"])
            if not start <= event_at <= end:
                continue
            records.append(
                {
                    "record_type": "network_marker",
                    "date": milestone["date"],
                    "value": 0,
                    "eip": eip["number"],
                    "eip_label": eip["label"],
                    "occurred_at": milestone["occurred_at"],
                    "event_label": milestone["label"],
                    "event_kind": milestone["kind"],
                    "status": milestone["status"],
                    "confidence": "high",
                    "rationale": "Network activation milestone",
                    "source_title": milestone["source_title"],
                    "source_url": milestone["provenance_url"],
                }
            )

        for marker in dataset.get("assessment_ref_markers", []):
            if int(marker["eip"]) != eip["number"]:
                continue
            event_at = parse_datetime(marker["occurred_at"])
            if not start <= event_at <= end:
                continue
            records.append(
                {
                    "record_type": "assessment_marker",
                    "date": chart_date(event_at),
                    "value": value_at(revisions, event_at, "substantive"),
                    "eip": eip["number"],
                    "eip_label": eip["label"],
                    **marker,
                }
            )

    return records, labels


def layer_chart(dataset: dict[str, Any], layer: str) -> alt.VConcatChart:
    domain = [dataset["plot"]["start_date"], dataset["plot"]["end_date"]]
    width = int(dataset["plot"]["width"])
    panel_height = int(dataset["plot"]["eip_panel_height"])
    if dataset.get("assessment_ref_markers"):
        panel_height += 48
    layer_eips = [eip for eip in dataset["eips"] if layer in eip["layers"]]
    layer_numbers = {eip["number"] for eip in layer_eips}

    strip_events = [
        {
            **milestone,
            "series": None,
        }
        for milestone in dataset["milestones"]
        if layer in milestone["layers"]
    ]
    strip_events.extend(
        {
            **devnet,
            "label": devnet["id"],
            "kind": "devnet",
        }
        for devnet in dataset["devnets"]
        if layer_numbers & set(devnet["participants"])
    )
    strip = event_strip(
        strip_events,
        domain=domain,
        width=width,
        title=f"{LAYER_NAMES[layer]} milestones and relevant devnets",
    )

    records, labels = layer_panel_records(dataset, layer)
    base = alt.Chart(alt.Data(values=records))
    x_no_axis = shared_x(domain, axis=False)

    curves = (
        base.transform_filter(alt.datum.record_type == "curve")
        .mark_line(interpolate="step-after")
        .encode(
            x=x_no_axis,
            y=alt.Y(
                "value:Q",
                title=None,
                scale=alt.Scale(zero=True, nice=True),
                axis=alt.Axis(
                    grid=True,
                    gridColor="#F1F5F9",
                    domain=False,
                    tickColor="#CBD5E1",
                    tickCount=4,
                ),
            ),
            color=alt.Color(
                "series:N",
                scale=alt.Scale(
                    domain=["All revisions", "Substantive revisions"],
                    range=["#CBD5E1", LAYER_COLORS[layer]],
                ),
                legend=alt.Legend(
                    title=None,
                    orient="top",
                    direction="horizontal",
                    symbolStrokeWidth=3,
                ),
            ),
            strokeWidth=alt.condition(
                alt.datum.series == "Substantive revisions", alt.value(2.8), alt.value(1.4)
            ),
            opacity=alt.condition(
                alt.datum.series == "Substantive revisions", alt.value(1), alt.value(0.8)
            ),
            tooltip=[
                alt.Tooltip("eip:N", title="EIP"),
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("value:Q", title="Cumulative revisions"),
            ],
        )
    )

    commit_points = (
        base.transform_filter(alt.datum.record_type == "commit")
        .mark_point(filled=True, size=34, stroke="white", strokeWidth=0.7)
        .encode(
            x=x_no_axis,
            y=alt.Y("value:Q", title=None),
            color=alt.Color(
                "semantic_effect:N",
                scale=alt.Scale(
                    domain=list(SEMANTIC_COLORS),
                    range=list(SEMANTIC_COLORS.values()),
                ),
                legend=alt.Legend(title="Commit classification", orient="top"),
            ),
            href=alt.Href("source_url:N"),
            tooltip=[
                alt.Tooltip("occurred_at:N", title="Committed (UTC)"),
                alt.Tooltip("event_kind:N", title="Change type"),
                alt.Tooltip("semantic_effect:N", title="Semantic effect"),
                alt.Tooltip("event_label:N", title="Summary"),
                alt.Tooltip("rationale:N", title="Classification rationale"),
                alt.Tooltip("confidence:N", title="Confidence"),
                alt.Tooltip("commit:N", title="Commit"),
                alt.Tooltip("source_url:N", title="Source"),
            ],
        )
    )

    creation_points = (
        base.transform_filter(alt.datum.record_type == "eip_marker")
        .mark_point(filled=True, size=100, color="#0F172A")
        .encode(
            x=x_no_axis,
            y=alt.Y("value:Q", title=None),
            shape=alt.Shape(
                "event_kind:N",
                scale=alt.Scale(
                    domain=["creation", "creation_before_window"],
                    range=["triangle-up", "triangle-left"],
                ),
                legend=None,
            ),
            href=alt.Href("source_url:N"),
            tooltip=[
                alt.Tooltip("event_label:N", title="Event"),
                alt.Tooltip("occurred_at:N", title="Actual creation commit"),
                alt.Tooltip("raw_label:N", title="Declared creation"),
                alt.Tooltip("source_url:N", title="Source"),
            ],
        )
    )

    inclusion_rules = (
        base.transform_filter(alt.datum.record_type == "inclusion_marker")
        .mark_rule(strokeWidth=1.4)
        .encode(
            x=x_no_axis,
            color=alt.condition(
                alt.datum.event_role != "state_transition",
                alt.value("#94A3B8"),
                alt.Color(
                    "event_kind:N",
                    scale=alt.Scale(
                        domain=list(INCLUSION_COLORS),
                        range=list(INCLUSION_COLORS.values()),
                    ),
                    legend=None,
                ),
            ),
            strokeDash=alt.condition(
                alt.datum.event_role != "state_transition",
                alt.value([3, 3]),
                alt.value([1, 0]),
            ),
            opacity=alt.condition(
                alt.datum.event_role != "state_transition",
                alt.value(0.35),
                alt.value(0.75),
            ),
            href=alt.Href("source_url:N"),
            tooltip=[
                alt.Tooltip("event_label:N", title="Normalized state"),
                alt.Tooltip("event_role_label:N", title="Event role"),
                alt.Tooltip("occurred_at:N", title="Recorded at"),
                alt.Tooltip("raw_label:N", title="Historical label"),
                alt.Tooltip("rationale:N", title="Normalization rationale"),
                alt.Tooltip("source_title:N", title="Source"),
                alt.Tooltip("source_url:N", title="Source URL"),
            ],
        )
    )

    inclusion_points = (
        base.transform_filter(
            (alt.datum.record_type == "inclusion_marker")
            & (alt.datum.event_role == "state_transition")
        )
        .mark_point(filled=True, size=70, stroke="white", strokeWidth=1)
        .encode(
            x=x_no_axis,
            y=alt.Y("value:Q", title=None),
            color=alt.Color(
                "event_kind:N",
                scale=alt.Scale(
                    domain=list(INCLUSION_COLORS),
                    range=list(INCLUSION_COLORS.values()),
                ),
                legend=alt.Legend(title="Inclusion-state transition", orient="top"),
            ),
            shape=alt.Shape(
                "event_kind:N",
                scale=alt.Scale(
                    domain=list(INCLUSION_COLORS),
                    range=["circle", "square", "diamond", "triangle-up", "cross", "cross", "cross", "stroke"],
                ),
                legend=None,
            ),
            href=alt.Href("source_url:N"),
            tooltip=[
                alt.Tooltip("event_label:N", title="Normalized state"),
                alt.Tooltip("event_role_label:N", title="Event role"),
                alt.Tooltip("occurred_at:N", title="Recorded at"),
                alt.Tooltip("raw_label:N", title="Historical label"),
                alt.Tooltip("rationale:N", title="Normalization rationale"),
                alt.Tooltip("source_url:N", title="Source"),
            ],
        )
    )

    inclusion_record_points = (
        base.transform_filter(
            (alt.datum.record_type == "inclusion_marker")
            & (alt.datum.event_role != "state_transition")
        )
        .mark_point(
            filled=False,
            size=52,
            color="#94A3B8",
            stroke="#64748B",
            strokeWidth=1.4,
        )
        .encode(
            x=x_no_axis,
            y=alt.Y("value:Q", title=None),
            href=alt.Href("source_url:N"),
            tooltip=[
                alt.Tooltip("event_label:N", title="Normalized state"),
                alt.Tooltip("event_role_label:N", title="Event role"),
                alt.Tooltip("occurred_at:N", title="Recorded at"),
                alt.Tooltip("raw_label:N", title="Historical label"),
                alt.Tooltip("rationale:N", title="Normalization rationale"),
                alt.Tooltip("source_url:N", title="Source"),
            ],
        )
    )

    devnet_points = (
        base.transform_filter(alt.datum.record_type == "devnet_marker")
        .mark_point(size=82, filled=True, stroke="white", strokeWidth=0.8)
        .encode(
            x=x_no_axis,
            y=alt.value(panel_height - 7),
            color=alt.Color(
                "event_kind:N",
                scale=alt.Scale(
                    domain=list(SERIES_COLORS),
                    range=list(SERIES_COLORS.values()),
                ),
                legend=alt.Legend(title="Devnet series", orient="top"),
            ),
            shape=alt.Shape(
                "status:N",
                scale=alt.Scale(domain=["actual", "planned"], range=["triangle-up", "diamond"]),
                legend=None,
            ),
            opacity=alt.condition(alt.datum.confidence == "medium", alt.value(0.55), alt.value(1)),
            href=alt.Href("source_url:N"),
            tooltip=[
                alt.Tooltip("event_label:N", title="Devnet"),
                alt.Tooltip("occurred_at:N", title="Launch / target"),
                alt.Tooltip("status:N", title="Status"),
                alt.Tooltip("confidence:N", title="Participation confidence"),
                alt.Tooltip("rationale:N", title="Participation evidence"),
                alt.Tooltip("source_title:N", title="Pinned source"),
                alt.Tooltip("source_url:N", title="Canonical source"),
                alt.Tooltip("provenance_url:N", title="Immutable provenance"),
            ],
        )
    )

    network_rules = (
        base.transform_filter(alt.datum.record_type == "network_marker")
        .mark_rule(strokeWidth=1, opacity=0.28)
        .encode(
            x=x_no_axis,
            color=alt.Color(
                "event_kind:N",
                scale=alt.Scale(
                    domain=list(MILESTONE_COLORS),
                    range=list(MILESTONE_COLORS.values()),
                ),
                legend=None,
            ),
            strokeDash=alt.condition(
                alt.datum.event_kind == "mainnet", alt.value([1, 0]), alt.value([4, 3])
            ),
            href=alt.Href("source_url:N"),
            tooltip=[
                alt.Tooltip("event_label:N", title="Network milestone"),
                alt.Tooltip("occurred_at:N", title="Activation"),
                alt.Tooltip("source_title:N", title="Source"),
                alt.Tooltip("source_url:N", title="Source URL"),
            ],
        )
    )

    assessment_tooltip = [
        alt.Tooltip("marker_kind:N", title="Assessment marker"),
        alt.Tooltip("occurred_at:N", title="Date / time (UTC)"),
        alt.Tooltip("event_label:N", title="Event"),
        alt.Tooltip("anchor_kind:N", title="Anchor kind"),
        alt.Tooltip("selection_mode:N", title="Selection mode"),
        alt.Tooltip("offset_from_anchor:N", title="Offset from anchor"),
        alt.Tooltip("commit:N", title="Selected commit"),
        alt.Tooltip("review_status:N", title="Review status"),
        alt.Tooltip("rationale:N", title="Rationale"),
        alt.Tooltip("source_url:N", title="Source"),
    ]

    selected_ref_rules = (
        base.transform_filter(
            (alt.datum.record_type == "assessment_marker")
            & (alt.datum.marker_kind == "Selected assessment ref")
        )
        .mark_rule(
            color=ASSESSMENT_MARKER_COLORS["Selected assessment ref"],
            strokeWidth=3.5,
            opacity=0.9,
        )
        .encode(
            x=x_no_axis,
            href=alt.Href("source_url:N"),
            tooltip=assessment_tooltip,
        )
    )

    anchor_rules = (
        base.transform_filter(
            (alt.datum.record_type == "assessment_marker")
            & (alt.datum.marker_kind == "Proposal anchor")
        )
        .mark_rule(
            color=ASSESSMENT_MARKER_COLORS["Proposal anchor"],
            strokeWidth=2,
            strokeDash=[5, 3],
            opacity=0.78,
        )
        .encode(
            x=x_no_axis,
            href=alt.Href("source_url:N"),
            tooltip=assessment_tooltip,
        )
    )

    selected_ref_flags = (
        base.transform_filter(
            (alt.datum.record_type == "assessment_marker")
            & (alt.datum.marker_kind == "Selected assessment ref")
        )
        .mark_point(
            shape="diamond",
            filled=True,
            size=520,
            color=ASSESSMENT_MARKER_COLORS["Selected assessment ref"],
            stroke="#701A75",
            strokeWidth=2.2,
        )
        .encode(
            x=x_no_axis,
            y=alt.value(14),
            href=alt.Href("source_url:N"),
            tooltip=assessment_tooltip,
        )
    )

    selected_ref_labels = (
        base.transform_filter(
            (alt.datum.record_type == "assessment_marker")
            & (alt.datum.marker_kind == "Selected assessment ref")
        )
        .mark_text(
            text="REF",
            color="white",
            fontSize=9,
            fontWeight="bold",
            baseline="middle",
        )
        .encode(
            x=x_no_axis,
            y=alt.value(14),
            href=alt.Href("source_url:N"),
            tooltip=assessment_tooltip,
        )
    )

    inclusion_stage_tooltip = [
        alt.Tooltip("event_label:N", title="Inclusion state"),
        alt.Tooltip("event_role_label:N", title="Event role"),
        alt.Tooltip("occurred_at:N", title="Recorded at"),
        alt.Tooltip("raw_label:N", title="Historical label"),
        alt.Tooltip("rationale:N", title="Normalization rationale"),
        alt.Tooltip("source_url:N", title="Source"),
    ]

    def inclusion_stage_flag(
        state: str,
        label: str,
        shape: str,
        color: str,
        y_position: int,
    ) -> tuple[alt.Chart, alt.Chart, alt.Chart]:
        stage_filter = (
            (alt.datum.record_type == "inclusion_marker")
            & (alt.datum.event_kind == state)
            & (alt.datum.event_role == "state_transition")
        )
        same_state_filter = (
            (alt.datum.record_type == "inclusion_marker")
            & (alt.datum.event_kind == state)
            & (alt.datum.event_role == "same_state_record")
        )
        point = (
            base.transform_filter(stage_filter)
            .mark_point(
                shape=shape,
                filled=True,
                size=430,
                color=color,
                stroke="#334155",
                strokeWidth=1.2,
            )
            .encode(
                x=x_no_axis,
                y=alt.value(y_position),
                href=alt.Href("source_url:N"),
                tooltip=inclusion_stage_tooltip,
            )
        )
        text = (
            base.transform_filter(stage_filter)
            .mark_text(
                text=label,
                color="white",
                fontSize=9,
                fontWeight="bold",
                baseline="middle",
            )
            .encode(
                x=x_no_axis,
                y=alt.value(y_position),
                href=alt.Href("source_url:N"),
                tooltip=inclusion_stage_tooltip,
            )
        )
        same_state_record = (
            base.transform_filter(same_state_filter)
            .mark_point(
                shape=shape,
                filled=False,
                size=150,
                color="#94A3B8",
                stroke="#64748B",
                strokeWidth=1.5,
            )
            .encode(
                x=x_no_axis,
                y=alt.value(y_position),
                href=alt.Href("source_url:N"),
                tooltip=inclusion_stage_tooltip,
            )
        )
        return point, text, same_state_record

    pfi_flag, pfi_label, pfi_same_state = inclusion_stage_flag(
        "proposed_for_inclusion",
        "PFI",
        "circle",
        INCLUSION_COLORS["proposed_for_inclusion"],
        40,
    )
    cfi_flag, cfi_label, cfi_same_state = inclusion_stage_flag(
        "considered_for_inclusion",
        "CFI",
        "square",
        INCLUSION_COLORS["considered_for_inclusion"],
        66,
    )
    sfi_flag, sfi_label, sfi_same_state = inclusion_stage_flag(
        "scheduled_for_inclusion",
        "SFI",
        "diamond",
        INCLUSION_COLORS["scheduled_for_inclusion"],
        92,
    )
    cfi_rip_suffix = (
        base.transform_filter(
            (alt.datum.record_type == "inclusion_marker")
            & (alt.datum.event_label == "CFI (RIP)")
            & (alt.datum.event_role == "state_transition")
        )
        .mark_text(
            text="(RIP)",
            color="#92400E",
            fontSize=8,
            fontWeight="bold",
            baseline="middle",
            dx=25,
        )
        .encode(
            x=x_no_axis,
            y=alt.value(66),
            href=alt.Href("source_url:N"),
            tooltip=inclusion_stage_tooltip,
        )
    )

    panels = (
        alt.layer(
            network_rules,
            curves,
            inclusion_rules,
            anchor_rules,
            selected_ref_rules,
            commit_points,
            creation_points,
            inclusion_points,
            inclusion_record_points,
            devnet_points,
            pfi_flag,
            pfi_label,
            pfi_same_state,
            cfi_flag,
            cfi_label,
            cfi_same_state,
            cfi_rip_suffix,
            sfi_flag,
            sfi_label,
            sfi_same_state,
            selected_ref_flags,
            selected_ref_labels,
        )
        .properties(width=width, height=panel_height)
        .facet(
            row=alt.Row(
                "eip_label:N",
                sort=labels,
                title=None,
                header=alt.Header(
                    labelAngle=0,
                    labelAlign="left",
                    labelAnchor="start",
                    labelColor="#0F172A",
                    labelFontSize=11,
                    labelFontWeight=600,
                    labelLimit=330,
                    labelPadding=8,
                ),
            )
        )
        .resolve_scale(y="independent")
        .properties(
            title=alt.TitleParams(
                f"{LAYER_NAMES[layer]} EIP revision histories",
                subtitle=[
                    "Primary line: cumulative substantive post-creation revisions. Faint line: all post-creation revisions.",
                    "Filled inclusion markers are state transitions; open gray markers preserve same-state records.",
                    "Triangles at panel bottoms are relevant devnets; lower opacity denotes medium-confidence participation.",
                    *(
                        [
                            "Assessment review lanes from top to bottom: REF, PFI, CFI, SFI, "
                            "then devnet/testnet markers.",
                            "Each event type has a fixed lane; the proposal anchor is the "
                            "amber dashed rule.",
                        ]
                        if dataset.get("assessment_ref_markers")
                        else []
                    ),
                ],
                anchor="start",
                color="#0F172A",
                fontSize=18,
                subtitleColor="#475569",
                subtitleFontSize=11,
            )
        )
    )

    return alt.vconcat(strip, panels, spacing=22).properties(
        title=alt.TitleParams(
            f"{dataset['fork']['display_name']} · {LAYER_NAMES[layer]}",
            subtitle=f"Shared calendar window {domain[0]} through {domain[1]} · {len(layer_eips)} EIPs",
            anchor="start",
            color="#0F172A",
            fontSize=24,
            subtitleColor="#475569",
            subtitleFontSize=12,
        )
    )


def aggregate_records(
    dataset: dict[str, Any], layer: str, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for eip in dataset["eips"]:
        if layer not in eip["layers"]:
            continue
        events.extend(
            event for event in eip["revisions"] if event["semantic_effect"] == "substantive"
        )
    events.sort(key=lambda event: (event["parsed_at"], event["eip"], event["id"]))
    running = sum(event["parsed_at"] <= start for event in events)
    records = [
        {
            "date": chart_date(start),
            "value": running,
            "layer": LAYER_NAMES[layer],
        }
    ]
    for event in events:
        if start < event["parsed_at"] <= end:
            running += 1
            records.append(
                {
                    "date": event["date"],
                    "value": running,
                    "layer": LAYER_NAMES[layer],
                }
            )
    records.append(
        {"date": chart_date(end), "value": running, "layer": LAYER_NAMES[layer]}
    )
    return records


def overview_chart(dataset: dict[str, Any]) -> alt.VConcatChart:
    start = parse_datetime(dataset["plot"]["start_date"])
    end = parse_datetime(dataset["plot"]["end_date"])
    domain = [dataset["plot"]["start_date"], dataset["plot"]["end_date"]]
    width = int(dataset["plot"]["width"])

    strip_events = [
        {**milestone, "series": None} for milestone in dataset["milestones"]
    ] + [
        {**devnet, "label": devnet["id"], "kind": "devnet"}
        for devnet in dataset["devnets"]
    ]
    strip = event_strip(
        strip_events,
        domain=domain,
        width=width,
        title="Fork milestones and devnet launches",
    )

    aggregates = aggregate_records(dataset, "execution", start, end)
    aggregates.extend(aggregate_records(dataset, "consensus", start, end))
    aggregate = (
        alt.Chart(alt.Data(values=aggregates))
        .mark_line(interpolate="step-after", strokeWidth=3)
        .encode(
            x=shared_x(domain, axis=False),
            y=alt.Y(
                "value:Q",
                title="Cumulative substantive revisions",
                axis=alt.Axis(domain=False, gridColor="#E2E8F0"),
            ),
            color=alt.Color(
                "layer:N",
                scale=alt.Scale(
                    domain=[LAYER_NAMES["execution"], LAYER_NAMES["consensus"]],
                    range=[LAYER_COLORS["execution"], LAYER_COLORS["consensus"]],
                ),
                legend=alt.Legend(title=None, orient="top"),
            ),
            tooltip=[
                alt.Tooltip("layer:N", title="Layer"),
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("value:Q", title="Cumulative substantive revisions"),
            ],
        )
        .properties(
            width=width,
            height=260,
            title=alt.TitleParams(
                "Aggregate specification activity by affected layer",
                subtitle="Cross-layer EIPs contribute to both lines; creation commits are excluded.",
                anchor="start",
                color="#0F172A",
                fontSize=16,
                subtitleColor="#475569",
                subtitleFontSize=11,
            ),
        )
    )

    activity_counter: Counter[tuple[str, str]] = Counter()
    activity_metadata: dict[tuple[str, str], dict[str, Any]] = {}
    overview_order = [
        eip["overview_label"]
        for eip in sorted(
            dataset["eips"],
            key=lambda item: (
                0 if item["layers"] == ["execution"] else 1 if len(item["layers"]) == 2 else 2,
                item["number"],
            ),
        )
    ]
    for eip in dataset["eips"]:
        for event in eip["revisions"]:
            if event["semantic_effect"] != "substantive" or not start <= event["parsed_at"] <= end:
                continue
            key = (eip["overview_label"], weekly_floor(event["parsed_at"]))
            activity_counter[key] += 1
            activity_metadata[key] = {
                "eip": eip["number"],
                "layers": layer_tag(eip["layers"]),
            }
    activity = [
        {
            "eip_label": label,
            "week": week,
            "week_end": (
                date.fromisoformat(week) + timedelta(days=7)
            ).isoformat(),
            "count": count,
            **activity_metadata[(label, week)],
        }
        for (label, week), count in sorted(activity_counter.items())
    ]
    heatmap = (
        alt.Chart(alt.Data(values=activity))
        .mark_rect(cornerRadius=1)
        .encode(
            x=alt.X(
                "week:T",
                title=None,
                scale=alt.Scale(domain=domain, nice=False),
                axis=alt.Axis(format="%b %Y", grid=False, tickCount=10, labelAngle=0),
            ),
            x2=alt.X2("week_end:T"),
            y=alt.Y(
                "eip_label:N",
                scale=alt.Scale(domain=overview_order),
                title=None,
                axis=alt.Axis(
                    domain=False,
                    ticks=False,
                    labelLimit=345,
                    labelPadding=6,
                    labelColor="#334155",
                ),
            ),
            color=alt.Color(
                "count:Q",
                scale=alt.Scale(scheme="blues", domainMin=0),
                legend=alt.Legend(title="Substantive commits / week", orient="top"),
            ),
            tooltip=[
                alt.Tooltip("eip:N", title="EIP"),
                alt.Tooltip("layers:N", title="Affected layers"),
                alt.Tooltip("week:T", title="Week starting"),
                alt.Tooltip("count:Q", title="Substantive revisions"),
            ],
        )
        .properties(
            width=width,
            height=max(260, len(overview_order) * 21),
            title=alt.TitleParams(
                "Weekly substantive revision activity",
                subtitle="Blank weeks have no substantive EIP-file revision; commit tooltips and provenance are in the layer figures.",
                anchor="start",
                color="#0F172A",
                fontSize=16,
                subtitleColor="#475569",
                subtitleFontSize=11,
            ),
        )
    )

    return alt.vconcat(strip, aggregate, heatmap, spacing=24).properties(
        title=alt.TitleParams(
            f"{dataset['fork']['display_name']} fork development overview",
            subtitle=f"Shared calendar window {domain[0]} through {domain[1]} · EIP-file history, inclusion decisions, devnets, and activations",
            anchor="start",
            color="#0F172A",
            fontSize=25,
            subtitleColor="#475569",
            subtitleFontSize=12,
        )
    )


def style(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    return (
        chart.configure(background="#FFFFFF")
        .configure_view(stroke=None)
        .configure_axis(
            labelFont="Arial",
            titleFont="Arial",
            titleColor="#334155",
            labelFontSize=10,
            titleFontSize=11,
        )
        .configure_legend(
            labelFont="Arial",
            titleFont="Arial",
            labelColor="#334155",
            titleColor="#334155",
            padding=4,
        )
        .configure_title(font="Arial", subtitleFont="Arial")
    )


def render_chart(chart: alt.TopLevelMixin, stem: Path) -> list[Path]:
    spec = chart.to_dict(validate=True)
    spec_path = stem.with_suffix(".vl.json")
    html_path = stem.with_suffix(".html")
    svg_path = stem.with_suffix(".svg")
    pdf_path = stem.with_suffix(".pdf")
    write_text(spec_path, json_text(spec))

    html = vlc.vegalite_to_html(spec, bundle=True)
    if isinstance(html, bytes):
        html = html.replace(
            b"<title>Chart</title>",
            f"<title>{stem.name}</title>".encode(),
            1,
        )
        write_bytes(html_path, html)
    else:
        html = html.replace("<title>Chart</title>", f"<title>{stem.name}</title>", 1)
        write_text(html_path, html)
    svg = vlc.vegalite_to_svg(spec)
    if isinstance(svg, bytes):
        write_bytes(svg_path, svg)
        svg_bytes = svg
    else:
        write_text(svg_path, svg)
        svg_bytes = svg.encode()
    # vl-convert's direct PDF output can vary between runs because its PDF
    # resource dictionary is unordered. Converting the deterministic SVG keeps
    # the PDF vector-based and gives stable bytes for manifests and archives.
    write_bytes(
        pdf_path,
        DeterministicPDFSurface.convert(bytestring=svg_bytes, dpi=72),
    )
    return [spec_path, html_path, svg_path, pdf_path]


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def render_fork(dataset: dict[str, Any], used_files: set[Path]) -> dict[str, Any]:
    fork_id = dataset["fork"]["id"]
    output_dir = OUTPUT_ROOT / fork_id
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / "plot-data.json"
    write_text(data_path, json_text(exportable_dataset(dataset)))

    artifacts = [data_path]
    charts = {
        "fork-overview": style(overview_chart(dataset)),
        "el-eip-histories": style(layer_chart(dataset, "execution")),
        "cl-eip-histories": style(layer_chart(dataset, "consensus")),
    }
    for name, chart in charts.items():
        artifacts.extend(render_chart(chart, output_dir / name))

    reproducibility_files = {
        TASK_ROOT / "pyproject.toml",
        TASK_ROOT / "uv.lock",
        Path(__file__).resolve(),
        *used_files,
    }
    manifest = {
        "schema_version": 1,
        "task_id": TASK_ID,
        "fork_id": fork_id,
        "determinism": {
            "generation_timestamp_recorded": False,
            "offline_html": True,
            "canonical_visual_specification": "Vega-Lite JSON",
        },
        "toolchain": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "altair": importlib.metadata.version("altair"),
            "cairosvg": importlib.metadata.version("cairosvg"),
            "vl-convert-python": importlib.metadata.version("vl-convert-python"),
            "pyyaml": importlib.metadata.version("pyyaml"),
        },
        "inputs": [
            {"path": rel(path), "sha256": file_sha256(path)}
            for path in sorted(reproducibility_files)
        ],
        "outputs": [
            {
                "path": artifact.relative_to(output_dir).as_posix(),
                "sha256": file_sha256(artifact),
                "bytes": artifact.stat().st_size,
            }
            for artifact in sorted(artifacts)
        ],
        "counts": {
            "eips": len(dataset["eips"]),
            "execution_eips": sum(
                "execution" in eip["layers"] for eip in dataset["eips"]
            ),
            "consensus_eips": sum(
                "consensus" in eip["layers"] for eip in dataset["eips"]
            ),
            "devnets": len(dataset["devnets"]),
            "milestones": len(dataset["milestones"]),
            "revision_events": sum(len(eip["revisions"]) for eip in dataset["eips"]),
            "substantive_revision_events": sum(
                event["semantic_effect"] == "substantive"
                for eip in dataset["eips"]
                for event in eip["revisions"]
            ),
        },
    }
    manifest_path = output_dir / "plot-manifest.yaml"
    write_text(
        manifest_path,
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=100),
    )
    return manifest


def configured_forks() -> list[str]:
    return sorted(path.stem for path in INPUT_ROOT.glob("*.yaml"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fork",
        action="append",
        choices=configured_forks(),
        help="Fork to build; repeat for multiple forks. Defaults to every configured fork.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate inputs and derived relationships without writing outputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    forks = args.fork or configured_forks()
    if not forks:
        raise InputError(f"No fork inputs found under {INPUT_ROOT}")
    for fork_id in forks:
        dataset, used_files = load_fork(INPUT_ROOT / f"{fork_id}.yaml")
        counts = {
            "EIPs": len(dataset["eips"]),
            "EL": sum("execution" in eip["layers"] for eip in dataset["eips"]),
            "CL": sum("consensus" in eip["layers"] for eip in dataset["eips"]),
            "devnets": len(dataset["devnets"]),
        }
        summary = ", ".join(f"{key}={value}" for key, value in counts.items())
        if args.validate_only:
            print(f"validated {fork_id}: {summary}")
        else:
            render_fork(dataset, used_files)
            print(f"rendered {fork_id}: {summary}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InputError as error:
        print(f"input error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
