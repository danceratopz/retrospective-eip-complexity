#!/usr/bin/env python3
"""Build review-gated Task 04 ref proposals from curated anchor decisions."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import yaml


TASK_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TASK_ROOT.parents[2]
TASK01_ROOT = REPO_ROOT / "research" / "tasks" / "01-fork-eip-history"
OUTPUT_ROOT = TASK_ROOT / "outputs" / "fork-eips"
DECISION_ROOT = TASK_ROOT / "outputs" / "anchor-decisions"
POLICY_PATH = TASK_ROOT / "outputs" / "anchor-fallback-policy.yaml"
EIPS_REPO = Path("/home/dtopz/code/github/EIPs")
GIT_REPOS = {
    "ethereum/EIPs": EIPS_REPO,
    "ethereum/execution-specs": Path("/home/dtopz/code/github/execution-specs"),
}
SUPPORTED_FORKS = ("prague", "amsterdam", "cancun", "shanghai")


class ProposalError(RuntimeError):
    """Raised when source records cannot support a proposal."""


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ProposalError(f"missing input: {path}")
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict):
        raise ProposalError(f"expected mapping in {path}")
    return value


def git(*args: str, repo: Path = EIPS_REPO, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=not binary,
    )
    return result.stdout


def parse_exact(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ProposalError(f"timestamp lacks a UTC offset: {value}")
    return parsed.astimezone(UTC)


def utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def event_time(value: str) -> tuple[datetime, datetime, str]:
    if len(value) == 10:
        day = date.fromisoformat(value)
        return (
            datetime.combine(day, time.min, UTC),
            datetime.combine(day, time.max, UTC),
            "day",
        )
    instant = parse_exact(value)
    return instant, instant, "instant"


def source_index(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {source["id"]: source for source in registry["sources"]}


def commit_time(commit: str, repo: Path = EIPS_REPO) -> datetime:
    return parse_exact(str(git("show", "-s", "--format=%cI", commit, repo=repo)).strip())


def revision_events(history: dict[str, Any]) -> list[dict[str, Any]]:
    events = list(history["revision_history"]["events"])
    if not events or events[0]["event_kind"] != "creation":
        raise ProposalError(f"EIP-{history['eip']['number']} has no leading creation event")
    for event in events:
        observed = commit_time(event["commit"])
        recorded = parse_exact(event["committed_at"])
        if observed != recorded:
            raise ProposalError(
                f"EIP-{history['eip']['number']} commit-time mismatch for {event['commit']}"
            )
        event["_utc"] = observed
    events.sort(key=lambda item: item["_utc"])
    return events


def revision_candidate(event: dict[str, Any], anchor_start: datetime) -> dict[str, Any]:
    committed = event["_utc"]
    return {
        "exists": True,
        "revision_event_id": event["id"],
        "event_kind": event["event_kind"],
        "commit": event["commit"],
        "committed_at": utc_text(committed),
        "offset_from_anchor_seconds": int((committed - anchor_start).total_seconds()),
        "semantic_effect": event["semantic_effect"],
        "summary": event["summary"],
        "immutable_url": (
            f"https://github.com/ethereum/EIPs/blob/{event['commit']}/{event['path']}"
        ),
        "source_ids": event["source_ids"],
    }


def missing_candidate() -> dict[str, Any]:
    return {
        "exists": False,
        "revision_event_id": None,
        "event_kind": None,
        "commit": None,
        "committed_at": None,
        "offset_from_anchor_seconds": None,
        "semantic_effect": None,
        "summary": None,
        "immutable_url": None,
        "source_ids": [],
    }


def validate_anchor_kind(
    decision: dict[str, Any], selected: dict[str, Any], all_events: list[dict[str, Any]]
) -> None:
    kind = decision["kind"]
    state = selected["normalized_state"]
    raw = selected["raw_label"].lower()
    proposals = [event for event in all_events if event["normalized_state"] == "proposed_for_inclusion"]
    considerations = [
        event for event in all_events if event["normalized_state"] == "considered_for_inclusion"
    ]
    if kind == "explicit_pfi" and not (
        state == "proposed_for_inclusion" and "proposed for inclusion" in raw
    ):
        raise ProposalError(f"{selected['id']} is not explicit PFI")
    if kind == "normalized_proposal_equivalent" and not (
        state == "proposed_for_inclusion" and "proposed for inclusion" not in raw
    ):
        raise ProposalError(f"{selected['id']} is not a normalized proposal equivalent")
    if kind == "fallback_cfi":
        if proposals or state != "considered_for_inclusion" or selected is not considerations[0]:
            raise ProposalError(f"{selected['id']} violates the frozen CFI fallback")
    if kind == "other" and (proposals or considerations):
        raise ProposalError(f"{selected['id']} bypasses an earlier policy rank")


def build_record(
    fork_id: str,
    relation: dict[str, Any],
    history: dict[str, Any],
    fork_sources: dict[str, dict[str, Any]],
    decision: dict[str, Any],
    run_at: str,
) -> dict[str, Any]:
    number = int(relation["eip"]["number"])
    inclusions = relation["inclusion_history"]["events"]
    matching = [event for event in inclusions if event["id"] == decision["selected_event_id"]]
    if len(matching) != 1:
        raise ProposalError(f"EIP-{number} selected event does not resolve uniquely")
    anchor_event = matching[0]
    validate_anchor_kind(decision, anchor_event, inclusions)

    alternative_ids = decision.get("alternative_event_ids", [])
    valid_ids = {event["id"] for event in inclusions}
    if any(event_id not in valid_ids for event_id in alternative_ids):
        raise ProposalError(f"EIP-{number} has an unknown alternative event ID")

    anchor_start, anchor_end, precision = event_time(str(anchor_event["occurred_at"]))
    recorded_at: str | None = None
    recorded_note = "Task 01 does not identify a distinct repository-recording commit."
    recorded_source_id = decision.get("recorded_commit_source_id")
    if recorded_source_id:
        source = fork_sources.get(recorded_source_id)
        if not source or source.get("source_type") != "git_commit":
            raise ProposalError(f"EIP-{number} has invalid recorded commit source {recorded_source_id}")
        source_repo = GIT_REPOS.get(source.get("repository"))
        if source_repo is None or not source_repo.is_dir():
            raise ProposalError(
                f"EIP-{number} cannot verify repository {source.get('repository')} for "
                f"{recorded_source_id}"
            )
        recorded = commit_time(source["commit"], source_repo)
        recorded_at = utc_text(recorded)
        recorded_note = (
            f"Repository recording time is the verified committer time of "
            f"{source['commit']} ({recorded_source_id})."
        )
        if decision["kind"] == "explicit_pfi" and precision == "instant" and recorded != anchor_start:
            raise ProposalError(f"EIP-{number} explicit PFI time differs from its recording commit")
    elif precision == "instant":
        recorded_at = utc_text(anchor_start)
        recorded_note = "Task 01 records an exact event instant; no different recording time is asserted."

    events = revision_events(history)
    if precision == "instant":
        preceding_events = [event for event in events if event["_utc"] <= anchor_start]
        following_events = [event for event in events if event["_utc"] > anchor_start]
        same_day_events: list[dict[str, Any]] = []
    else:
        preceding_events = [event for event in events if event["_utc"] < anchor_start]
        following_events = [event for event in events if event["_utc"] > anchor_end]
        same_day_events = [event for event in events if anchor_start <= event["_utc"] <= anchor_end]

    preceding_event = preceding_events[-1] if preceding_events else None
    following_event = following_events[0] if following_events else None
    preceding = revision_candidate(preceding_event, anchor_start) if preceding_event else missing_candidate()
    following = revision_candidate(following_event, anchor_start) if following_event else missing_candidate()

    unknowns = list(decision.get("unknowns", []))
    if precision == "day":
        unknowns.append(
            "The Task 01 anchor has calendar-day precision only. Offsets use 00:00:00 UTC as a "
            "display boundary, not as an inferred decision time. Revisions on the anchor day are "
            "excluded from both definite brackets."
        )
    if same_day_events:
        ids = ", ".join(event["id"] for event in same_day_events)
        unknowns.append(
            f"Anchor-day revision ordering is unresolved at Task 01 precision: {ids}. Human review "
            "must decide whether any of these events preceded the inclusion decision."
        )

    if preceding_event:
        selected_event = preceding_event
        selection_mode = "preceding"
        post_exception = {
            "used": False,
            "within_seven_days": False,
            "diff_semantic_effect": None,
            "diff_summary": None,
            "hindsight_risk": None,
            "justification": None,
        }
    else:
        selected_event = events[0]
        selection_mode = "post_anchor_exception"
        delta = int((selected_event["_utc"] - anchor_start).total_seconds())
        within = 0 <= delta <= 7 * 86_400
        exception_review = decision.get("post_anchor_exception_review", {})
        post_exception = {
            "used": True,
            "within_seven_days": within,
            "diff_semantic_effect": selected_event["semantic_effect"],
            "diff_summary": exception_review.get("diff_summary", selected_event["summary"]),
            "hindsight_risk": exception_review.get("hindsight_risk") or (
                "The EIP file did not have a definitely preceding repository revision at the "
                "available anchor precision, so this ref may contain information unavailable when "
                "the proposal state took effect."
            ),
            "justification": exception_review.get("justification") or (
                "Task 04 requires the creation revision when no preceding candidate exists; human "
                "review is mandatory and this proposal does not self-approve the exception."
            ),
        }
        unknowns.append("No definitely preceding EIP-file revision exists at the verified anchor precision.")

    selected_time = selected_event["_utc"]
    selected_path = selected_event["path"]
    selected_commit = selected_event["commit"]
    blob_sha = str(git("rev-parse", f"{selected_commit}:{selected_path}")).strip()
    content = git("show", f"{selected_commit}:{selected_path}", binary=True)
    assert isinstance(content, bytes)
    content_sha256 = hashlib.sha256(content).hexdigest()
    selected_offset = int((selected_time - anchor_start).total_seconds())
    immutable_url = f"https://github.com/ethereum/EIPs/blob/{selected_commit}/{selected_path}"

    review_status = decision.get("review_status", "proposed")
    ambiguity_codes = decision.get("ambiguity_codes", [])
    if selection_mode == "post_anchor_exception" or same_day_events:
        review_status = "needs_human_review"
    if review_status not in {"proposed", "needs_human_review"}:
        raise ProposalError(f"EIP-{number} cannot be generated with review status {review_status}")

    cutoff = utc_text(anchor_start) if precision == "instant" else str(anchor_event["occurred_at"])
    if selection_mode == "post_anchor_exception":
        cutoff = utc_text(selected_time)

    date_basis = (
        f"Task 01 event {anchor_event['id']} records {anchor_event['occurred_at']} with {precision} "
        f"precision. {recorded_note} No time is derived from an EIP frontmatter date, author time, "
        "pull-request opening time, client history, or observed outcome."
    )
    verification_rationale = (
        f"The selected event resolves in the Task 01 fork–EIP record and cites primary source IDs "
        f"{', '.join(anchor_event['source_ids'])}. The frozen policy classifies it as "
        f"{decision['kind']}. {decision['rationale']}"
    )
    if recorded_source_id:
        verification_rationale += (
            " The cited Git recording commit was independently resolved in the pinned "
            "ethereum/EIPs clone."
        )

    selected_source_ids = selected_event["source_ids"]
    selected_revision = {
        "revision_event_id": selected_event["id"],
        "event_kind": selected_event["event_kind"],
        "repository": "ethereum/EIPs",
        "commit": selected_commit,
        "path": selected_path,
        "committed_at": utc_text(selected_time),
        "offset_from_anchor_seconds": selected_offset,
        "git_blob_sha": blob_sha,
        "content_sha256": content_sha256,
        "immutable_url": immutable_url,
        "source_ids": selected_source_ids,
    }

    rationale = (
        f"The complete Task 01 EIP history was normalized to UTC and bracketed against "
        f"{anchor_event['id']}. "
    )
    if selection_mode == "preceding":
        rationale += (
            f"The default preceding rule selects {selected_event['id']} at {utc_text(selected_time)}. "
            "No post-anchor exception is proposed."
        )
    else:
        rationale += (
            "No definite preceding revision exists, so the creation exception is proposed for human review."
        )
    if precision == "day":
        rationale += " The anchor's day precision and any same-day ordering limitation remain explicit."

    notes = [
        "This generated record is a proposal only. It becomes authoritative only after separate human approval.",
        f"Frozen anchor policy: task04-anchor-fallback-v1; ambiguity codes: {', '.join(ambiguity_codes) or 'none'}.",
        *decision.get("spot_check_notes", []),
    ]
    unknowns.extend(relation.get("unknowns", []))

    return {
        "schema_version": 1,
        "task_id": "04-complexity-assessment-ref-selection",
        "fork_id": fork_id,
        "eip": {
            "number": number,
            "title": relation["eip"]["title"],
            "layers": relation["eip"]["layers"],
        },
        "inputs": {
            "fork_eip_record": f"research/tasks/01-fork-eip-history/outputs/fork-eips/{fork_id}/eip-{number}.yaml",
            "eip_history_record": f"research/tasks/01-fork-eip-history/outputs/eips/eip-{number}.yaml",
        },
        "research_run": {
            "started_at": run_at,
            "completed_at": run_at,
            "researcher": "Codex coordinator (Task 04 proposal generation)",
        },
        "anchor": {
            "target_state": "proposed_for_inclusion",
            "selected_event_id": anchor_event["id"],
            "alternative_event_ids": alternative_ids,
            "kind": decision["kind"],
            "raw_label": anchor_event["raw_label"],
            "effective_at": str(anchor_event["occurred_at"]),
            "recorded_at": recorded_at,
            "date_basis": date_basis,
            "verification_status": decision["verification_status"],
            "verification_rationale": verification_rationale,
            "confidence": decision["confidence"],
            "source_ids": anchor_event["source_ids"],
        },
        "bracketing_revisions": {"preceding": preceding, "following": following},
        "selection": {
            "mode": selection_mode,
            "selected_revision": selected_revision,
            "information_cutoff_at": cutoff,
            "rationale": rationale,
            "confidence": decision["confidence"],
            "post_anchor_exception": post_exception,
        },
        "review": {
            "status": review_status,
            "reviewer": None,
            "reviewed_at": None,
            "notes": notes,
        },
        "unknowns": unknowns,
    }


def run(fork_id: str) -> None:
    policy = load_yaml(POLICY_PATH)
    if policy.get("policy_id") != "task04-anchor-fallback-v1":
        raise ProposalError("the frozen anchor policy is missing or unexpected")
    decisions = load_yaml(DECISION_ROOT / f"{fork_id}.yaml")
    if decisions.get("fork_id") != fork_id or decisions.get("policy_id") != policy["policy_id"]:
        raise ProposalError("decision file identity or policy mismatch")
    run_at = decisions["research_run_at"]
    decision_by_eip = {int(item["eip"]): item for item in decisions["anchors"]}

    relation_dir = TASK01_ROOT / "outputs" / "fork-eips" / fork_id
    relations = [load_yaml(path) for path in sorted(relation_dir.glob("eip-*.yaml"))]
    relations = [relation for relation in relations if "execution" in relation["eip"]["layers"]]
    expected = {int(relation["eip"]["number"]) for relation in relations}
    if expected != set(decision_by_eip):
        raise ProposalError(
            f"decision inventory mismatch for {fork_id}: missing={sorted(expected-set(decision_by_eip))}, "
            f"extra={sorted(set(decision_by_eip)-expected)}"
        )

    fork_registry = source_index(
        load_yaml(TASK01_ROOT / "outputs" / "sources" / "forks" / f"{fork_id}.yaml")
    )
    target_dir = OUTPUT_ROOT / fork_id
    target_dir.mkdir(parents=True, exist_ok=True)
    for relation in sorted(relations, key=lambda item: int(item["eip"]["number"])):
        number = int(relation["eip"]["number"])
        history = load_yaml(TASK01_ROOT / "outputs" / "eips" / f"eip-{number}.yaml")
        output = build_record(
            fork_id, relation, history, fork_registry, decision_by_eip[number], run_at
        )
        path = target_dir / f"eip-{number}.yaml"
        if path.exists():
            current = load_yaml(path)
            if current.get("review", {}).get("status") == "approved":
                raise ProposalError(f"refusing to overwrite approved record: {path}")
        path.write_text(yaml.safe_dump(output, sort_keys=False, width=100))
        print(f"wrote {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fork", required=True, choices=SUPPORTED_FORKS)
    args = parser.parse_args()
    run(args.fork)


if __name__ == "__main__":
    main()
