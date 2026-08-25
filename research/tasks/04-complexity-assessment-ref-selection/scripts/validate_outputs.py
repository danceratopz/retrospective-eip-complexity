#!/usr/bin/env python3
"""Validate Task 04 outputs using only Task 01 and Task 04 evidence.

Task 03 consistency is validated separately by ``render_review.py --validate-only``.
This validator deliberately has no path or import for Task 02 or Task 05.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import yaml


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK01_ROOT = REPO_ROOT / "research" / "tasks" / "01-fork-eip-history"
REF_ROOT = TASK_ROOT / "outputs" / "fork-eips"
EIPS_REPO = Path("/home/dtopz/code/github/EIPs")
FORKS = ("amsterdam", "osaka", "prague", "cancun", "shanghai")


class ValidationError(RuntimeError):
    """Raised for an invalid Task 04 output."""


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise ValidationError(f"expected mapping in {path}")
    return value


def parse_exact(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValidationError(f"timestamp lacks offset: {value}")
    return parsed.astimezone(UTC)


def anchor_bounds(value: str) -> tuple[datetime, datetime, bool]:
    if len(value) == 10:
        day = date.fromisoformat(value)
        return datetime.combine(day, time.min, UTC), datetime.combine(day, time.max, UTC), True
    instant = parse_exact(value)
    return instant, instant, False


def git(*args: str, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(EIPS_REPO), *args],
        check=True,
        capture_output=True,
        text=not binary,
    )
    return result.stdout


def event_times(history: dict[str, Any]) -> list[tuple[dict[str, Any], datetime]]:
    result = []
    for event in history["revision_history"]["events"]:
        result.append((event, parse_exact(event["committed_at"])))
    return sorted(result, key=lambda item: item[1])


def validate_record(
    fork: str,
    relation: dict[str, Any],
    history: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    number = int(relation["eip"]["number"])
    if record["fork_id"] != fork or int(record["eip"]["number"]) != number:
        raise ValidationError(f"identity mismatch for {fork}/EIP-{number}")
    if record["eip"]["title"] != relation["eip"]["title"]:
        raise ValidationError(f"title mismatch for {fork}/EIP-{number}")
    if record["eip"]["layers"] != relation["eip"]["layers"]:
        raise ValidationError(f"layer mismatch for {fork}/EIP-{number}")

    inclusions = relation["inclusion_history"]["events"]
    anchor = record["anchor"]
    matches = [event for event in inclusions if event["id"] == anchor["selected_event_id"]]
    if len(matches) != 1:
        raise ValidationError(f"anchor does not resolve for {fork}/EIP-{number}")
    event = matches[0]
    if str(event["occurred_at"]) != str(anchor["effective_at"]):
        raise ValidationError(f"anchor time mismatch for {fork}/EIP-{number}")
    if event["raw_label"] != anchor["raw_label"]:
        raise ValidationError(f"anchor label mismatch for {fork}/EIP-{number}")

    proposals = [item for item in inclusions if item["normalized_state"] == "proposed_for_inclusion"]
    considerations = [
        item for item in inclusions if item["normalized_state"] == "considered_for_inclusion"
    ]
    kind = anchor["kind"]
    raw = event["raw_label"].lower()
    state = event["normalized_state"]
    policy_deviation: str | None = None
    if kind == "explicit_pfi" and not (
        state == "proposed_for_inclusion" and "proposed for inclusion" in raw
    ):
        policy_deviation = "explicit_pfi_without_literal_task01_pfi"
    if kind == "normalized_proposal_equivalent" and not (
        state == "proposed_for_inclusion" and "proposed for inclusion" not in raw
    ):
        policy_deviation = "historical_equivalent_without_task01_proposal_event"
    if kind == "fallback_cfi" and (
        proposals or not considerations or event["id"] != considerations[0]["id"]
    ):
        policy_deviation = "cfi_fallback_bypasses_higher_rank_or_earlier_cfi"
    if kind == "other" and (proposals or considerations):
        policy_deviation = "other_anchor_bypasses_higher_policy_rank"
    if kind not in {
        "explicit_pfi",
        "normalized_proposal_equivalent",
        "fallback_cfi",
        "other",
    }:
        raise ValidationError(f"unknown anchor kind for {fork}/EIP-{number}: {kind}")
    if policy_deviation and fork != "osaka":
        raise ValidationError(
            f"anchor-policy deviation for {fork}/EIP-{number}: {policy_deviation}"
        )

    revisions = event_times(history)
    start, end, day_precision = anchor_bounds(str(anchor["effective_at"]))
    if day_precision:
        preceding = [item for item in revisions if item[1] < start]
        following = [item for item in revisions if item[1] > end]
    else:
        preceding = [item for item in revisions if item[1] <= start]
        following = [item for item in revisions if item[1] > start]
    expected_preceding = preceding[-1][0]["id"] if preceding else None
    expected_following = following[0][0]["id"] if following else None
    actual_preceding = record["bracketing_revisions"]["preceding"]["revision_event_id"]
    actual_following = record["bracketing_revisions"]["following"]["revision_event_id"]
    if actual_preceding != expected_preceding or actual_following != expected_following:
        raise ValidationError(f"revision bracket mismatch for {fork}/EIP-{number}")

    selected = record["selection"]["selected_revision"]
    selected_matches = [item for item in revisions if item[0]["id"] == selected["revision_event_id"]]
    if len(selected_matches) != 1:
        raise ValidationError(f"selected revision missing for {fork}/EIP-{number}")
    selected_event, selected_time = selected_matches[0]
    if selected_event["commit"] != selected["commit"] or selected_event["path"] != selected["path"]:
        raise ValidationError(f"selected revision identity mismatch for {fork}/EIP-{number}")
    observed_time = parse_exact(str(git("show", "-s", "--format=%cI", selected["commit"])).strip())
    if observed_time != selected_time or observed_time != parse_exact(selected["committed_at"]):
        raise ValidationError(f"selected revision time mismatch for {fork}/EIP-{number}")
    expected_offset = int((selected_time - start).total_seconds())
    if int(selected["offset_from_anchor_seconds"]) != expected_offset:
        raise ValidationError(f"selected offset mismatch for {fork}/EIP-{number}")

    blob = str(git("rev-parse", f"{selected['commit']}:{selected['path']}")).strip()
    content = git("show", f"{selected['commit']}:{selected['path']}", binary=True)
    assert isinstance(content, bytes)
    if selected["git_blob_sha"] != blob:
        raise ValidationError(f"blob SHA mismatch for {fork}/EIP-{number}")
    if selected["content_sha256"] != hashlib.sha256(content).hexdigest():
        raise ValidationError(f"content SHA mismatch for {fork}/EIP-{number}")
    expected_url = (
        f"https://github.com/ethereum/EIPs/blob/{selected['commit']}/{selected['path']}"
    )
    if selected["immutable_url"] != expected_url:
        raise ValidationError(f"immutable URL mismatch for {fork}/EIP-{number}")

    mode = record["selection"]["mode"]
    if expected_preceding:
        if mode != "preceding" or selected["revision_event_id"] != expected_preceding:
            raise ValidationError(f"default preceding rule mismatch for {fork}/EIP-{number}")
    elif mode != "post_anchor_exception" or selected_event["event_kind"] != "creation":
        raise ValidationError(f"creation exception mismatch for {fork}/EIP-{number}")
    review = record["review"]
    status = review["status"]
    if status not in {"proposed", "needs_human_review", "approved"}:
        raise ValidationError(f"unknown review status for {fork}/EIP-{number}: {status}")
    if status == "approved":
        if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
            raise ValidationError(f"approved record lacks reviewer for {fork}/EIP-{number}")
        try:
            date.fromisoformat(review["reviewed_at"])
        except (TypeError, ValueError) as error:
            raise ValidationError(
                f"approved record lacks review date for {fork}/EIP-{number}"
            ) from error
    elif review.get("reviewer") is not None or review.get("reviewed_at") is not None:
        raise ValidationError(f"unapproved record has review metadata for {fork}/EIP-{number}")
    if mode == "post_anchor_exception" and status not in {
        "needs_human_review",
        "approved",
    }:
        raise ValidationError(f"unreviewed exception status for {fork}/EIP-{number}")

    if fork == "osaka" and status != "approved":
        raise ValidationError(f"approved Osaka status changed for EIP-{number}")

    following_record = record["bracketing_revisions"]["following"]
    near_substantive = bool(
        following_record["exists"]
        and 0 < int(following_record["offset_from_anchor_seconds"]) <= 7 * 86_400
        and following_record["semantic_effect"] in {"substantive", "uncertain"}
    )
    return {
        "number": number,
        "anchor_kind": kind,
        "selection_mode": mode,
        "review_status": status,
        "selected_commit": selected["commit"],
        "content_sha256": selected["content_sha256"],
        "near_substantive_following": near_substantive,
        "exception_within_seven_days": record["selection"]["post_anchor_exception"][
            "within_seven_days"
        ],
        "policy_deviation": policy_deviation,
    }


def main() -> None:
    summary: dict[str, Any] = {"forks": {}, "shared_eips": {}, "errors": []}
    occurrences: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for fork in FORKS:
        relation_dir = TASK01_ROOT / "outputs" / "fork-eips" / fork
        relations = [load_yaml(path) for path in sorted(relation_dir.glob("eip-*.yaml"))]
        relations = [item for item in relations if "execution" in item["eip"]["layers"]]
        relation_by_number = {int(item["eip"]["number"]): item for item in relations}
        paths = sorted((REF_ROOT / fork).glob("eip-*.yaml"))
        records = [load_yaml(path) for path in paths]
        actual = {int(item["eip"]["number"]): item for item in records}
        if set(actual) != set(relation_by_number):
            raise ValidationError(
                f"inventory mismatch for {fork}: missing={sorted(set(relation_by_number)-set(actual))}, "
                f"extra={sorted(set(actual)-set(relation_by_number))}"
            )
        details = []
        for number in sorted(actual):
            history = load_yaml(TASK01_ROOT / "outputs" / "eips" / f"eip-{number}.yaml")
            detail = validate_record(
                fork, relation_by_number[number], history, actual[number]
            )
            details.append(detail)
            occurrences[number].append({"fork": fork, **detail})
        summary["forks"][fork] = {
            "record_count": len(details),
            "anchor_kinds": dict(Counter(item["anchor_kind"] for item in details)),
            "selection_modes": dict(Counter(item["selection_mode"] for item in details)),
            "review_statuses": dict(Counter(item["review_status"] for item in details)),
            "near_substantive_following": [
                item["number"] for item in details if item["near_substantive_following"]
            ],
            "post_anchor_exceptions": [
                {
                    "eip": item["number"],
                    "within_seven_days": item["exception_within_seven_days"],
                }
                for item in details
                if item["selection_mode"] == "post_anchor_exception"
            ],
            "legacy_policy_deviations": [
                {"eip": item["number"], "reason": item["policy_deviation"]}
                for item in details
                if item["policy_deviation"]
            ],
        }
    summary["shared_eips"] = {
        str(number): items for number, items in sorted(occurrences.items()) if len(items) > 1
    }
    summary["total_records"] = sum(
        item["record_count"] for item in summary["forks"].values()
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
