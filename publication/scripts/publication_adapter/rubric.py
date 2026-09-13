"""Shared criterion registry and rubric-revision definitions.

Both checklist revisions of the STEEL complexity-assessment template are represented so that revision-1
human checklists and revision-2 LLM assessments can be rendered with the same criterion metadata. The
registry order is the site-wide stable criterion order: revision 2 order, with the revision-1-only
"Engine API encoding changes" row placed directly after "Engine API changes".
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import TASK05_RUBRIC, TASK05C, BuildError, load_yaml, source


REVISION_2_ORDER = [
    "evm_gas_rule_changes",
    "state_access_ordering_within_opcode_execution",
    "blob_gas_accounting_changes",
    "state_gas_accounting_changes",
    "new_evm_gas_refund",
    "patterns_affecting_pre_existing_tests",
    "new_invariant_on_pre_existing_tests",
    "transition_tool_interface_changes",
    "new_test_framework_primitives",
    "cryptography",
    "edge_boundary_conditions",
    "block_syncing_changes",
    "engine_api_changes",
    "added_system_contracts",
    "modified_system_contracts",
    "added_opcodes",
    "modified_opcodes",
    "added_precompiles",
    "modified_precompiles",
    "encoding_changes_rlp_ssz",
    "new_transaction_types",
    "new_or_modified_transaction_validity_mechanisms",
    "new_block_header_fields",
    "new_fork_activation_mechanism",
    "performance_risks",
    "security_risks",
    "unspecified_behavior_requiring_cross_client_consensus",
    "cross_eip_interactions",
]
REVISION_1_ORDER = [
    "evm_gas_rule_changes",
    "blob_gas_accounting_changes",
    "new_evm_gas_refund",
    "patterns_affecting_pre_existing_tests",
    "transition_tool_interface_changes",
    "cryptography",
    "edge_boundary_conditions",
    "block_syncing_changes",
    "engine_api_changes",
    "engine_api_encoding_changes",
    "added_system_contracts",
    "modified_system_contracts",
    "added_opcodes",
    "modified_opcodes",
    "added_precompiles",
    "modified_precompiles",
    "encoding_changes_rlp_ssz",
    "new_transaction_types",
    "new_or_modified_transaction_validity_mechanisms",
    "new_block_header_fields",
    "new_fork_activation_mechanism",
    "performance_risks",
    "security_risks",
    "cross_eip_interactions",
]
REGISTRY_ORDER = [
    *REVISION_2_ORDER[: REVISION_2_ORDER.index("engine_api_changes") + 1],
    "engine_api_encoding_changes",
    *REVISION_2_ORDER[REVISION_2_ORDER.index("engine_api_changes") + 1 :],
]
UNCAPPED = {"cross_eip_interactions"}
LABEL_OVERRIDES = {"cryptography": "Cryptography"}

TIER_THRESHOLDS = {
    1: {"low": {"minimum": 0, "maximum": 9}, "medium": {"minimum": 10, "maximum": 19}, "high": {"minimum": 20, "maximum": None}},
    2: {"low": {"minimum": 0, "maximum": 11}, "medium": {"minimum": 12, "maximum": 22}, "high": {"minimum": 23, "maximum": None}},
}
NOMINAL_MAXIMUM = {1: 72, 2: 84}
RUBRIC_ORDER = {1: REVISION_1_ORDER, 2: REVISION_2_ORDER}
TIERS = ["low", "medium", "high"]


def tier_for(score: int, revision: int) -> str:
    for tier in TIERS:
        limits = TIER_THRESHOLDS[revision][tier]
        if score >= limits["minimum"] and (limits["maximum"] is None or score <= limits["maximum"]):
            return tier
    raise BuildError(f"score {score} matches no tier in revision {revision}")


def _split_definition(body: str) -> tuple[str, dict[str, str], list[str]]:
    """Split a rubric definition body into its lead sentence, anchor texts, and footnotes."""
    lead: list[str] = []
    anchors: dict[str, str] = {}
    notes: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        anchor = re.match(r"^- (\d+)\.\s*(.+)$", stripped)
        if anchor:
            anchors[anchor.group(1)] = anchor.group(2).strip()
        elif stripped.startswith("- **+1"):
            notes.append(stripped.lstrip("- ").replace("**", ""))
        elif stripped.startswith("*"):
            notes.append(stripped.lstrip("*").strip())
        elif not anchors:
            lead.append(stripped)
        else:
            notes.append(stripped)
    return " ".join(lead), anchors, notes


def _revision_2_definitions() -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    manifest_path = TASK05_RUBRIC / "manifest.yaml"
    view_path = TASK05_RUBRIC / "assessor-view.md"
    manifest = load_yaml(manifest_path)
    text = view_path.read_text(encoding="utf-8")
    anchors_start = text.index("#### Anchors")
    checklist_start = text.index("### Checklist")
    section = text[anchors_start:checklist_start]
    headings = list(re.finditer(r"^##### (.+?)\s*$", section, re.MULTILINE))
    definitions: dict[str, dict[str, Any]] = {}
    heading_to_id = {
        "Cryptography": "cryptography",
    }
    labels_by_heading = {label_for_heading(item): item for item in REVISION_2_ORDER}
    for index, match in enumerate(headings):
        heading = match.group(1).strip()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(section)
        body = section[match.end() : end]
        criterion_id = heading_to_id.get(heading) or labels_by_heading.get(heading)
        if criterion_id is None:
            raise BuildError(f"unknown revision-2 rubric heading: {heading}")
        lead, anchors, notes = _split_definition(body)
        definitions[criterion_id] = {"label": heading, "short_definition": lead, "anchors": anchors, "notes": notes}
    if set(definitions) != set(REVISION_2_ORDER):
        raise BuildError("revision-2 rubric definitions do not cover the checklist")
    rubric_source = manifest["source"]
    return (
        definitions,
        {
            "repository": rubric_source["repository"],
            "commit": rubric_source["repository_commit"],
            "path": rubric_source["path"],
            "immutable_url": rubric_source["immutable_url"],
            "checklist_revision": rubric_source["checklist_revision"],
        },
        [source(manifest_path), source(view_path)],
    )


def label_for_heading(criterion_id: str) -> str:
    """Return the revision-2 heading text for a criterion id (data-driven labels are preferred)."""
    return {
        "evm_gas_rule_changes": "EVM Gas rule changes",
        "state_access_ordering_within_opcode_execution": "State-access ordering within opcode execution",
        "blob_gas_accounting_changes": "Blob gas accounting changes",
        "state_gas_accounting_changes": "State gas accounting changes",
        "new_evm_gas_refund": "New EVM gas refund",
        "patterns_affecting_pre_existing_tests": "Patterns affecting pre-existing tests",
        "new_invariant_on_pre_existing_tests": "New invariant on pre-existing tests",
        "transition_tool_interface_changes": "Transition-tool interface changes",
        "new_test_framework_primitives": "New test-framework primitives",
        "cryptography": "Cryptography",
        "edge_boundary_conditions": "Edge/boundary conditions",
        "block_syncing_changes": "Block syncing changes",
        "engine_api_changes": "Engine API changes",
        "engine_api_encoding_changes": "Engine API encoding changes",
        "added_system_contracts": "Added system contracts",
        "modified_system_contracts": "Modified system contracts",
        "added_opcodes": "Added opcodes",
        "modified_opcodes": "Modified opcodes",
        "added_precompiles": "Added precompiles",
        "modified_precompiles": "Modified precompiles",
        "encoding_changes_rlp_ssz": "Encoding changes (RLP/SSZ)",
        "new_transaction_types": "New transaction types",
        "new_or_modified_transaction_validity_mechanisms": "New or modified transaction validity mechanisms",
        "new_block_header_fields": "New block / header fields",
        "new_fork_activation_mechanism": "New fork activation mechanism",
        "performance_risks": "Performance risks",
        "security_risks": "Security risks",
        "unspecified_behavior_requiring_cross_client_consensus": "Unspecified behavior requiring cross-client consensus",
        "cross_eip_interactions": "Cross-EIP interactions",
    }[criterion_id]


def _revision_1_definitions() -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    path = TASK05C / "inputs/rubrics/template-d936bcb34963cb5eec015dada2e4188e49fc14d5.yaml"
    template = load_yaml(path)
    if template["anchor_order"] != REVISION_1_ORDER:
        raise BuildError("revision-1 rubric order differs from the registry")
    if template["tier_thresholds"] != TIER_THRESHOLDS[1] or template["maximum_score"] != NOMINAL_MAXIMUM[1]:
        raise BuildError("revision-1 rubric thresholds differ from the registry")
    definitions: dict[str, dict[str, Any]] = {}
    for anchor in template["anchors"]:
        lead, anchors, notes = _split_definition(anchor["definition"] or "")
        definitions[anchor["id"]] = {
            "label": anchor["label"],
            "short_definition": lead,
            "anchors": anchors,
            "notes": notes,
            "definition_present": anchor["definition_present"],
        }
    return (
        definitions,
        {
            "repository": template["repository"],
            "commit": template["commit"],
            "path": template["path"],
            "immutable_url": template["immutable_url"],
            "checklist_revision": 1,
            "known_source_defects": template["known_source_defects"],
        },
        [source(path)],
    )


def build_rubrics() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    """Return (criteria registry, rubric revisions, consumed sources)."""
    definitions_2, source_2, sources_2 = _revision_2_definitions()
    definitions_1, source_1, sources_1 = _revision_1_definitions()
    criteria: list[dict[str, Any]] = []
    for criterion_id in REGISTRY_ORDER:
        primary = definitions_2.get(criterion_id) or definitions_1[criterion_id]
        revisions = [revision for revision, order in RUBRIC_ORDER.items() if criterion_id in order]
        label = LABEL_OVERRIDES.get(criterion_id, primary["label"])
        entry = {
            "id": criterion_id,
            "label": label,
            "short_definition": primary["short_definition"] or f"{label} (the revision-1 template defines no anchor text for this row).",
            "anchors": primary["anchors"],
            "notes": primary["notes"],
            "rubric_revisions": revisions,
            "uncapped": criterion_id in UNCAPPED,
            "definition_present": bool(primary["short_definition"] or primary["anchors"]),
        }
        if criterion_id in definitions_1 and criterion_id in definitions_2 and definitions_1[criterion_id]["anchors"] != definitions_2[criterion_id]["anchors"]:
            entry["revision_1_anchors"] = definitions_1[criterion_id]["anchors"]
        criteria.append(entry)
    rubrics = {
        str(revision): {
            "revision": revision,
            "criteria": RUBRIC_ORDER[revision],
            "criterion_count": len(RUBRIC_ORDER[revision]),
            "nominal_maximum": NOMINAL_MAXIMUM[revision],
            "tier_thresholds": TIER_THRESHOLDS[revision],
            "source": source_1 if revision == 1 else source_2,
        }
        for revision in (1, 2)
    }
    return criteria, rubrics, sources_1 + sources_2
