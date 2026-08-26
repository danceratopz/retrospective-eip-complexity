#!/usr/bin/env -S uv run --script
#
# /// script
# dependencies = [
#   "pyyaml",
#   "pandas",
# ]
# ///
"""Task 07: compute candidate observed-effort metrics (observed-metrics-v0).

Reads ONLY Tasks 01/03/04/04b canonical outputs. This script must never read
Task 05 assessment outputs: metric gathering stays blind to predicted scores.

See TASK.md for metric definitions and rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

TASK_DIR = Path(__file__).resolve().parent.parent
TASKS = TASK_DIR.parent
T01 = TASKS / "01-fork-eip-history" / "outputs"
T03 = TASKS / "03-fork-development-timelines" / "inputs" / "forks"
T04 = TASKS / "04-complexity-assessment-ref-selection" / "outputs" / "fork-eips"
T04B = TASKS / "04b-fork-evaluation-cutoffs" / "outputs" / "forks"
OUT = TASK_DIR / "outputs"

FORKS = ["shanghai", "cancun", "prague", "osaka", "amsterdam"]
CALCULATION_VERSION = "observed-metrics-v0"
CENSOR_AT = datetime(2026, 8, 25, tzinfo=timezone.utc)

STATE_RANK = {
    "proposed_for_inclusion": 1,
    "considered_for_inclusion": 2,
    "scheduled_for_inclusion": 3,
    "included": 4,
}

METRIC_COLUMNS = [
    "days_cutoff_to_mainnet",
    "subst_revisions_after_cutoff",
    "normative_revisions_after_cutoff",
    "devnet_count",
    "devnet_span_days",
    "days_cutoff_to_first_devnet",
    "deps_final",
    "deps_after_cutoff",
    "inclusion_reversals",
    "days_cutoff_to_sfi",
]


def parse_dt(value) -> datetime | None:
    """Parse ISO date or timestamp; day-precision normalizes to 00:00:00Z."""
    if value is None:
        return None
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh)


def days(a: datetime, b: datetime) -> float:
    return round((b - a).total_seconds() / 86400, 1)


def compute_row(fork: str, ref_path: Path, fork_input: dict,
                mainnet: tuple[str, datetime] | None,
                cohorts: dict) -> dict:
    rec = load(ref_path)
    n = rec["eip"]["number"]
    if rec["review"]["status"] != "approved":
        raise SystemExit(f"{fork} eip-{n}: Task 04 record not approved")
    cutoff = parse_dt(rec["selection"]["information_cutoff_at"])
    censored = mainnet is None
    window_end = mainnet[1] if mainnet else CENSOR_AT

    hist_path = T01 / "eips" / f"eip-{n}.yaml"
    hist = load(hist_path)
    subst_ids, norm_ids, uncertain = [], [], 0
    for ev in hist.get("revision_history", {}).get("events", []):
        at = parse_dt(ev.get("committed_at") or ev.get("authored_at"))
        if at is None or not (cutoff < at <= window_end):
            continue
        effect = ev.get("semantic_effect")
        if effect == "substantive":
            subst_ids.append(ev["id"])
            if ev.get("change_type") == "normative_behavior":
                norm_ids.append(ev["id"])
        elif effect == "uncertain":
            uncertain += 1

    first_dep_evidence: dict[int, datetime] = {}
    for ev in (hist.get("dependency_history") or {}).get("events", []):
        if ev.get("relationship") not in ("requires", "interacts_with"):
            continue
        at = parse_dt(ev.get("occurred_at"))
        if at is None or at > window_end:
            continue
        t = ev["target_eip"]
        if t not in first_dep_evidence or at < first_dep_evidence[t]:
            first_dep_evidence[t] = at
    dep_targets = set(first_dep_evidence)
    deps_after = {t for t, at in first_dep_evidence.items() if at > cutoff}

    fe_path = T01 / "fork-eips" / fork / f"eip-{n}.yaml"
    fe = load(fe_path)
    seq, sfi, unknown_incl = [], None, 0
    for ev in fe.get("inclusion_history", {}).get("events", []):
        st, at = ev.get("normalized_state"), parse_dt(ev.get("occurred_at"))
        if st == "unknown":
            unknown_incl += 1
        if st in STATE_RANK and at is not None:
            seq.append((at, STATE_RANK[st], ev.get("id")))
            if st == "scheduled_for_inclusion" and sfi is None:
                sfi = (at, ev.get("id"))
    seq.sort(key=lambda t: t[0])
    reversals = sum(1 for i in range(1, len(seq)) if seq[i][1] < seq[i - 1][1])

    parts = sorted(
        ((parse_dt(d["occurred_at"]), d["id"]) for d in fork_input.get("devnets", [])
         if n in (d.get("participation") or [])),
    )
    def inferred_eips(d: dict) -> set:
        out = set()
        for e in d.get("inferred_participation") or []:
            out.add(e.get("eip") if isinstance(e, dict) else e)
        return out

    inferred = sum(1 for d in fork_input.get("devnets", []) if n in inferred_eips(d))

    cohort, late_cls = cohorts.get(n, (None, None))
    rel = lambda p: str(p.relative_to(TASKS.parent.parent))  # noqa: E731
    return {
        "fork": fork,
        "eip": n,
        "cross_layer": "consensus" in rec["eip"].get("layers", []),
        "cohort": cohort,
        "late_classification": late_cls,
        "censored": censored,
        "inputs": {
            "task04_record": rel(ref_path),
            "eip_history_record": rel(hist_path),
            "fork_eip_record": rel(fe_path),
            "fork_timeline_input": rel(T03 / f"{fork}.yaml"),
        },
        "window": {
            "information_cutoff_at": cutoff.isoformat(),
            "window_end_at": window_end.isoformat(),
            "window_end_kind": "mainnet" if mainnet else "censor",
            "mainnet_milestone_id": mainnet[0] if mainnet else None,
        },
        "metrics": {
            "days_cutoff_to_mainnet": days(cutoff, mainnet[1]) if mainnet else None,
            "days_cutoff_to_window_end": days(cutoff, window_end),
            "subst_revisions_after_cutoff": len(subst_ids),
            "normative_revisions_after_cutoff": len(norm_ids),
            "uncertain_revisions_after_cutoff": uncertain,
            "devnet_count": len(parts),
            "devnet_span_days": days(parts[0][0], parts[-1][0]) if parts else None,
            "inferred_devnet_count": inferred,
            "days_cutoff_to_first_devnet": days(cutoff, parts[0][0]) if parts else None,
            "deps_final": len(dep_targets),
            "deps_after_cutoff": len(deps_after),
            "inclusion_reversals": reversals,
            "unknown_inclusion_events": unknown_incl,
            "days_cutoff_to_sfi": days(cutoff, sfi[0]) if sfi else None,
        },
        "evidence": {
            "substantive_revision_event_ids": subst_ids,
            "normative_revision_event_ids": norm_ids,
            "devnet_ids": [i for _, i in parts],
            "dependency_target_eips": sorted(dep_targets),
            "dependency_targets_after_cutoff": sorted(deps_after),
            "sfi_event_id": sfi[1] if sfi else None,
        },
    }


def main() -> None:
    rows = []
    for fork in FORKS:
        fork_input = load(T03 / f"{fork}.yaml")
        mainnet = None
        for ms in fork_input.get("milestones", []):
            if ms.get("kind") == "mainnet":
                mainnet = (ms["id"], parse_dt(ms["occurred_at"]))
        cohorts = {}
        b = T04B / f"{fork}.yaml"
        if b.exists():
            for e in load(b).get("eips", []):
                late = e.get("late_scope") or {}
                cohorts[e["number"]] = (e.get("cohort"), late.get("classification"))
        for ref_path in sorted((T04 / fork).glob("eip-*.yaml")):
            rows.append(compute_row(fork, ref_path, fork_input, mainnet, cohorts))

    OUT.mkdir(parents=True, exist_ok=True)
    doc = {
        "schema_version": 1,
        "task_id": "07-observed-effort-metrics",
        "calculation_version": CALCULATION_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "censor_at": CENSOR_AT.isoformat(),
        "score_blind": True,
        "row_count": len(rows),
        "rows": rows,
    }
    with (OUT / "observed-metrics.yaml").open("w") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False, default_flow_style=False, width=110)

    flat = [
        {"fork": r["fork"], "eip": r["eip"], "cross_layer": r["cross_layer"],
         "cohort": r["cohort"], "late_classification": r["late_classification"],
         "censored": r["censored"],
         "information_cutoff_at": r["window"]["information_cutoff_at"],
         **r["metrics"]}
        for r in rows
    ]
    df = pd.DataFrame(flat)
    df.to_csv(OUT / "observed-metrics.csv", index=False)

    pct = df.copy()
    for c in METRIC_COLUMNS:
        pct[c] = df.groupby("fork")[c].rank(pct=True)
    pct.to_csv(OUT / "observed-metrics-withinfork-pct.csv", index=False)

    print(f"{len(rows)} rows -> {OUT / 'observed-metrics.yaml'}")
    print(df.groupby("fork")["eip"].count().to_string())


if __name__ == "__main__":
    main()
