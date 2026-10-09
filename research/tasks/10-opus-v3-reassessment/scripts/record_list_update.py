#!/usr/bin/env python3
"""Record a later EIP-8081 list state against the frozen Task 10 Hegotá assessments.

    record_list_update.py --eips-repo ../EIPs --commit f154af816c4e3467ea3a86e064e4d3493ab2a8e0 --label "ACDE 247"

Assessments stay at the snapshot commit; only list membership (SFI, CFI, PFI, DFI) moves. EIPs that joined a
list after the snapshot are recorded as not assessed, never as zero.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import common
from common import load_yaml, rel, yaml_bytes
from engine_adapter import TASK_ROOT
from prepare import COHORT_PATH, eip8081_lists


OUTPUT_ROOT = TASK_ROOT / "prospective" / "outputs" / "list-updates"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eips-repo", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--label", required=True, help="Decision that produced the update, for example 'ACDE 247'")
    args = parser.parse_args()
    cohort = load_yaml(COHORT_PATH)
    snapshot = {item["eip"]: item["eip_8081_list"] for item in cohort["inventory"]}
    source, rows = eip8081_lists(args.eips_repo.resolve(), args.commit)
    current = {row["eip"]: row for row in rows}
    in_scope = set(common.config()["prospective"]["lists"])
    changes = []
    for eip in sorted(set(snapshot) | {eip for eip, row in current.items() if row["list"] in in_scope}):
        before = snapshot.get(eip)
        after = current[eip]["list"] if eip in current else None
        if before != after:
            changes.append(
                {
                    "eip": eip,
                    "listed_title": current[eip]["listed_title"] if eip in current else None,
                    "from": before,
                    "to": after,
                    "assessed": eip in snapshot,
                }
            )
    record = {
        "schema_version": 1,
        "task_id": common.TASK_ID,
        "snapshot_id": cohort["snapshot_id"],
        "label": args.label,
        "source": source,
        "assessments_unchanged": True,
        "note": "List membership only. Assessments remain those of the snapshot commit; EIPs added after it are not assessed.",
        "lists": {
            name: [row["eip"] for row in rows if row["list"] == name] for name in ("SFI", "CFI", "PFI", "DFI")
        },
        "changes": changes,
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_ROOT / f"{source['committed_at'][:10]}-{args.commit[:7]}.yaml"
    path.write_bytes(yaml_bytes(record))
    print(f"wrote {rel(path)}: {len(changes)} changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
