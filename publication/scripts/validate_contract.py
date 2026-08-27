#!/usr/bin/env python3
"""Validate the static publication contract without third-party dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


PUBLICATION_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PUBLICATION_ROOT.parent
VERSION = "1.1.0"
JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"

RECORD_TYPES = {
    "study_metadata",
    "fork",
    "global_eip",
    "fork_eip_assessment",
    "result_summary",
    "chart_data_index",
    "data_catalog_entry",
    "empty_prospective_status",
    "prospective_cohort_summary",
    "prospective_eip_assessment",
}
ROUTE_FAMILIES = {
    "landing",
    "study",
    "fork_index",
    "fork_detail",
    "fork_eip_assessment",
    "global_eip_index",
    "global_eip_detail",
    "result_predicted_complexity",
    "result_observed_effort",
    "result_predicted_vs_observed",
    "result_human_alignment",
    "prospective_hegota",
}
LABEL_KEYS = {
    "historical_retrospective",
    "prospective",
    "provisional",
    "forecastable_at_cutoff",
    "late_scope",
    "censored",
    "right_censored",
    "potentially_in_sample",
    "not_applicable_to_el_rubric",
    "under_specified",
    "canonical",
    "derived",
    "observed_effort_proxy",
}
DISPOSITIONS = {
    "public_metadata",
    "public_body",
    "reference_only",
    "excluded",
    "blocked",
}
MATURITIES = {
    "approved",
    "provisional",
    "validated_unfrozen",
    "empty_reserved",
}
RELEASE_STATES = {
    "contract_internal",
    "local_preview",
    "review_artifact",
    "publication_ready",
    "public",
}
TASK_FAMILIES = {
    "01-fork-eip-history",
    "03-fork-development-timelines",
    "04-complexity-assessment-ref-selection",
    "04b-fork-evaluation-cutoffs",
    "05-retrospective-complexity-assignment",
    "05c-amsterdam-human-assessment-alignment",
    "07-observed-effort-metrics",
    "08-hegota-prospective-complexity-assessment",
}
EXPECTED_JSON_FILES = {
    "contract/adapter-boundary.json",
    "contract/labels.json",
    "contract/routes.json",
    "contract/source-dispositions.json",
    "fixtures/publication-record.invalid.json",
    "fixtures/publication-record.valid.json",
    "schemas/publication-record.schema.json",
}
EXPECTED_INVALID_CODES = {
    "blocked_source_public_body",
    "forbidden_key",
    "forbidden_value",
    "prospective_empty_state",
    "prospective_score",
    "schema_violation",
    "source_path_not_relative",
}
DENY_SCAN_TERMS = {
    "session_id": "session_id",
    "local_home_path": "/home/dtopz",
    "temporary_path": "/tmp",
    "local_file_url": "file://",
    "credentials": "credentials",
    "task08_approved_path": "research/tasks/08-hegota-prospective-complexity-assessment",
}


class ContractError(RuntimeError):
    """Raised when the publication contract is inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=unique_object
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot parse {path.relative_to(PUBLICATION_ROOT)}: {error}") from error


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def is_commit(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def is_repository_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value or value.startswith("/"):
        return False
    path = Path(value)
    return not path.is_absolute() and ".." not in path.parts


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_ref(schema_root: dict[str, Any], reference: str) -> dict[str, Any]:
    require(reference.startswith("#/"), f"unsupported schema reference: {reference}")
    current: Any = schema_root
    for part in reference[2:].split("/"):
        current = current[part.replace("~1", "/").replace("~0", "~")]
    require(isinstance(current, dict), f"schema reference is not an object: {reference}")
    return current


def matches_type(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    raise ContractError(f"unsupported schema type in project validator: {expected}")


def schema_errors(
    instance: Any,
    schema: dict[str, Any],
    schema_root: dict[str, Any],
    location: str = "$",
) -> list[str]:
    if "$ref" in schema:
        return schema_errors(instance, resolve_ref(schema_root, schema["$ref"]), schema_root, location)

    errors: list[str] = []
    if "type" in schema and not matches_type(instance, schema["type"]):
        return [f"{location}: expected {schema['type']}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{location}: expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{location}: value is outside the enum")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{location}: string is too short")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append(f"{location}: string does not match pattern")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{location}: number is below minimum")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{location}: array has too few items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{location}: array has too many items")
        if schema.get("uniqueItems"):
            frozen = [json.dumps(item, sort_keys=True) for item in instance]
            if len(frozen) != len(set(frozen)):
                errors.append(f"{location}: array items are not unique")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(
                    schema_errors(item, schema["items"], schema_root, f"{location}[{index}]")
                )
    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{location}: missing required key {key}")
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                errors.extend(
                    schema_errors(value, properties[key], schema_root, f"{location}.{key}")
                )
            elif schema.get("additionalProperties") is False:
                errors.append(f"{location}: unexpected key {key}")
    for child_schema in schema.get("allOf", []):
        errors.extend(schema_errors(instance, child_schema, schema_root, location))
    if "if" in schema:
        condition_errors = schema_errors(instance, schema["if"], schema_root, location)
        if not condition_errors and "then" in schema:
            errors.extend(schema_errors(instance, schema["then"], schema_root, location))
        if condition_errors and "else" in schema:
            errors.extend(schema_errors(instance, schema["else"], schema_root, location))
    return errors


def route_regex(path_pattern: str) -> re.Pattern[str]:
    escaped = re.escape(path_pattern)
    parameterized = re.sub(r"\\\{[a-z_]+\\\}", r"[^/]+", escaped)
    return re.compile(f"^{parameterized}$")


def recursive_items(value: Any, path: str = "$") -> list[tuple[str, str | None, Any]]:
    items: list[tuple[str, str | None, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            items.append((child_path, key, child))
            items.extend(recursive_items(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            items.append((child_path, None, child))
            items.extend(recursive_items(child, child_path))
    return items


def validate_record(
    record: dict[str, Any],
    schema: dict[str, Any],
    routes: dict[str, Any],
    labels: dict[str, Any],
    adapter: dict[str, Any],
    dispositions: dict[str, Any],
) -> tuple[set[str], list[str]]:
    codes: set[str] = set()
    details: list[str] = []
    project_schema_errors = schema_errors(record, schema, schema)
    if project_schema_errors:
        codes.add("schema_violation")
        details.extend(project_schema_errors)

    record_type = record.get("record_type")
    if record.get("schema_version") != VERSION:
        codes.add("schema_version")
    if record_type not in RECORD_TYPES:
        codes.add("unknown_record_type")
    if not is_commit(record.get("source_commit")):
        codes.add("source_commit")
    if record.get("canonical_or_derived") not in {"canonical", "derived"}:
        codes.add("canonical_or_derived")
    if record.get("maturity") not in MATURITIES:
        codes.add("maturity")
    if record.get("public_download_disposition") not in DISPOSITIONS:
        codes.add("disposition")

    label_values = record.get("labels")
    if not isinstance(label_values, list) or any(label not in LABEL_KEYS for label in label_values):
        codes.add("label")
        label_values = []
    elif label_values != sorted(label_values):
        codes.add("unstable_label_order")
    label_definitions = {item["key"]: item for item in labels["labels"]}
    for label in label_values:
        mutual = set(label_definitions[label]["mutually_exclusive_with"])
        if mutual & set(label_values):
            codes.add("mutually_exclusive_labels")
        if record_type not in label_definitions[label]["applicable_record_types"]:
            codes.add("label_record_type")
    ownership = record.get("canonical_or_derived")
    if ownership in {"canonical", "derived"} and ownership not in label_values:
        codes.add("ownership_label")

    matching_routes = [
        route
        for route in routes["route_families"]
        if isinstance(record.get("route"), str)
        and route_regex(route["path_pattern"]).fullmatch(record["route"])
    ]
    matching_routes = [
        route for route in matching_routes if route["source_record_type"] == record_type
    ]
    if record_type not in {"chart_data_index", "empty_prospective_status", "prospective_eip_assessment"} and len(matching_routes) != 1:
        codes.add("route")
    if matching_routes:
        missing_labels = set(matching_routes[0]["required_labels"]) - set(label_values)
        if missing_labels:
            codes.add("route_required_labels")

    source_entries = {item["source_identifier"]: item for item in dispositions["entries"]}
    source_records = record.get("source_records")
    if not isinstance(source_records, list) or not source_records:
        codes.add("source_records")
        source_records = []
    else:
        paths = [item.get("source_path") for item in source_records if isinstance(item, dict)]
        if paths != sorted(paths):
            codes.add("unstable_source_order")
    for source_record in source_records:
        if not isinstance(source_record, dict):
            codes.add("source_records")
            continue
        path = source_record.get("source_path")
        if not is_repository_relative(path):
            codes.add("source_path_not_relative")
        if not is_sha256(source_record.get("sha256")):
            codes.add("source_sha256")
        identifiers = source_record.get("source_identifiers")
        if not isinstance(identifiers, list) or not identifiers:
            codes.add("source_identifier")
            continue
        for identifier in identifiers:
            entry = source_entries.get(identifier)
            if entry is None:
                codes.add("unknown_source_identifier")
                continue
            proposed = entry["proposed_publication_disposition"]
            if proposed in {"blocked", "excluded"}:
                if record.get("public_download_disposition") == "public_body":
                    codes.add("blocked_source_public_body")
                else:
                    codes.add("blocked_source")
            if record.get("public_download_disposition") == "public_body" and proposed != "public_body":
                if proposed not in {"blocked", "excluded"}:
                    codes.add("source_not_approved_for_body")

    forbidden = adapter["forbidden_public_content"]
    exact_keys = set(forbidden["forbidden_key_names"])
    key_patterns = [re.compile(pattern) for pattern in forbidden["forbidden_key_patterns"]]
    value_patterns = [re.compile(pattern) for pattern in forbidden["forbidden_value_patterns"]]
    for location, key, value in recursive_items(record):
        if key is not None:
            if key in exact_keys or any(pattern.search(key) for pattern in key_patterns):
                codes.add("forbidden_key")
                details.append(f"{location}: forbidden key")
            if re.fullmatch(r"(?i)prospective_.*score", key):
                codes.add("prospective_score")
        if isinstance(value, str):
            if any(pattern.search(value) for pattern in value_patterns):
                codes.add("forbidden_value")
                details.append(f"{location}: forbidden value")
    payload = record.get("payload", {})
    if record.get("route") == "/prospective/hegota/":
        if (
            record_type != "prospective_cohort_summary"
            or payload.get("snapshot_id") != adapter["prospective_gate"]["snapshot_id"]
            or payload.get("population_count") != 44
            or payload.get("scored_count") != 37
            or payload.get("not_applicable_count") != 7
            or payload.get("el_rubric_total") != 776
            or record.get("maturity") != "approved"
        ):
            codes.add("prospective_empty_state")

    if "not_applicable_to_el_rubric" in label_values:
        score_keys = {
            key
            for _, key, value in recursive_items(payload)
            if key in {"score", "primary_score"} and isinstance(value, (int, float))
        }
        if score_keys:
            codes.add("not_applicable_score")
    if any(
        isinstance(item, dict)
        and isinstance(item.get("source_path"), str)
        and item["source_path"].startswith("research/tasks/04b-fork-evaluation-cutoffs/")
        for item in source_records
    ) and "provisional" not in label_values:
        codes.add("provisional_label")
    flat_strings = [
        value.lower()
        for _, _, value in recursive_items(record)
        if isinstance(value, str)
    ]
    if "observed_effort_proxy" in label_values and any("amsterdam" in value for value in flat_strings):
        if not {"right_censored", "potentially_in_sample"} <= set(label_values):
            codes.add("amsterdam_caveat_labels")
    return codes, details


def validate_routes_labels_adapter(
    routes: dict[str, Any], labels: dict[str, Any], adapter: dict[str, Any], schema: dict[str, Any]
) -> None:
    for name, document in (
        ("routes", routes),
        ("labels", labels),
        ("adapter", adapter),
        ("schema", schema),
    ):
        require(document.get("schema_version") == VERSION, f"{name}: unexpected schema version")

    route_items = routes.get("route_families")
    require(isinstance(route_items, list), "routes: route_families must be a list")
    route_keys = [item.get("key") for item in route_items]
    require(len(route_keys) == len(set(route_keys)), "routes: duplicate route family")
    require(set(route_keys) == ROUTE_FAMILIES, "routes: route family enum mismatch")
    route_paths = [item.get("path_pattern") for item in route_items]
    require(len(route_paths) == len(set(route_paths)), "routes: duplicate path pattern")
    templates = {item["key"] for item in routes.get("page_templates", [])}
    require(len(templates) == len(routes.get("page_templates", [])), "routes: duplicate template")
    for route in route_items:
        require(route["source_record_type"] in RECORD_TYPES, f"routes: unknown record type for {route['key']}")
        require(route["template"] in templates, f"routes: unknown template for {route['key']}")
        require(set(route["required_labels"]) <= LABEL_KEYS, f"routes: unknown label for {route['key']}")
        require(set(route["allowed_cross_links"]) <= ROUTE_FAMILIES, f"routes: broken cross-link for {route['key']}")
        parameters = re.findall(r"\{([a-z_]+)\}", route["path_pattern"])
        require(parameters == route["parameters"], f"routes: parameter mismatch for {route['key']}")
    for nav in routes.get("global_navigation", []):
        require(nav["route_family"] in ROUTE_FAMILIES, "routes: navigation target is unknown")
    release_items = routes.get("release_states", [])
    release_keys = [item.get("key") for item in release_items]
    require(set(release_keys) == RELEASE_STATES and len(release_keys) == len(set(release_keys)), "routes: release states mismatch")
    require(routes.get("release_state") == "local_preview", "routes: release state must be local_preview")
    owner_states = {item["key"]: item["owner_authorization_required"] for item in release_items}
    require(owner_states["publication_ready"] and owner_states["public"], "routes: owner gates are missing")

    label_items = labels.get("labels")
    require(isinstance(label_items, list), "labels: labels must be a list")
    label_keys = [item.get("key") for item in label_items]
    require(len(label_keys) == len(set(label_keys)), "labels: duplicate key")
    require(set(label_keys) == LABEL_KEYS, "labels: label enum mismatch")
    label_map = {item["key"]: item for item in label_items}
    for item in label_items:
        require(item["requirement"] in {"required", "optional", "mutually_exclusive"}, f"labels: requirement invalid for {item['key']}")
        require(set(item["applicable_record_types"]) <= RECORD_TYPES, f"labels: record type invalid for {item['key']}")
        require(set(item["mutually_exclusive_with"]) <= LABEL_KEYS, f"labels: mutual exclusion invalid for {item['key']}")
        require(bool(item["minimum_visible_caveat"]), f"labels: caveat missing for {item['key']}")
        require(bool(item["allowed_treatments"]), f"labels: treatments missing for {item['key']}")
        require(bool(item["prohibited_substitutions"]), f"labels: substitutions missing for {item['key']}")
        for other in item["mutually_exclusive_with"]:
            require(item["key"] in label_map[other]["mutually_exclusive_with"], f"labels: asymmetric exclusion {item['key']} / {other}")
    for route in route_items:
        for label_key in route["required_labels"]:
            require(route["source_record_type"] in label_map[label_key]["applicable_record_types"], f"labels: {label_key} cannot label {route['key']}")

    task_items = adapter.get("allowed_input_task_families")
    task_ids = [item.get("task_id") for item in task_items]
    require(set(task_ids) == TASK_FAMILIES and len(task_ids) == len(set(task_ids)), "adapter: task family enum mismatch")
    roots: list[str] = []
    for item in task_items:
        require(bool(item["allowed_record_classes"]), f"adapter: no record classes for {item['task_id']}")
        for root in item["exact_repository_relative_roots"]:
            require(is_repository_relative(root), f"adapter: non-relative input root: {root}")
            roots.append(root)
    require(len(roots) == len(set(roots)), "adapter: duplicate input root")
    require(adapter.get("direction") == "one_way_read_only", "adapter: direction mismatch")
    require(adapter["canonical_and_derived_ownership"].get("research_writes_permitted") is False, "adapter: research writes must be forbidden")
    adapter_maturities = adapter.get("maturity_enum", [])
    require(
        set(adapter_maturities) == MATURITIES
        and len(adapter_maturities) == len(set(adapter_maturities)),
        "adapter: maturity enum mismatch",
    )
    output_items = adapter.get("output_record_types")
    output_types = [item.get("record_type") for item in output_items]
    require(set(output_types) == RECORD_TYPES and len(output_types) == len(set(output_types)), "adapter: output type enum mismatch")
    route_map = {item["key"]: item for item in route_items}
    for output in output_items:
        route_refs = output.get("route_families", [])
        require(route_refs or output.get("non_page_role"), f"adapter: {output['record_type']} lacks route or non-page role")
        for route_key in route_refs:
            require(route_key in ROUTE_FAMILIES, f"adapter: unknown route {route_key}")
            require(route_map[route_key]["source_record_type"] == output["record_type"], f"adapter: route/type mismatch for {route_key}")
    output_route_refs = {
        route_key for output in output_items for route_key in output.get("route_families", [])
    }
    require(output_route_refs == ROUTE_FAMILIES, "adapter: not every route is owned by an output type")
    require(set(adapter["public_output_allowlist"]["allowed_record_types"]) == RECORD_TYPES, "adapter: public record allowlist mismatch")
    require(adapter["public_output_allowlist"].get("deny_by_default") is True, "adapter: deny-by-default missing")
    require(adapter["public_output_allowlist"].get("recursive_research_copy_permitted") is False, "adapter: recursive research copy must be forbidden")
    gate = adapter["prospective_gate"]
    require(gate["allowed_record_type_now"] == "prospective_cohort_summary", "adapter: prospective summary type mismatch")
    require(gate["reserved_route_family"] == "prospective_hegota", "adapter: prospective route mismatch")
    require(gate["snapshot_id"] == "hegota-pfi-2026-08-26-ac450a4", "adapter: prospective snapshot mismatch")
    require(gate["population_count"] == 44, "adapter: prospective population mismatch")
    require(gate["assessment_count"] == 37, "adapter: prospective assessment count mismatch")
    require(gate["not_applicable_count"] == 7, "adapter: prospective N/A count mismatch")
    require(gate["el_rubric_total"] == 776, "adapter: prospective score sum mismatch")
    require(gate["validation_result"] == "pass", "adapter: prospective validation gate mismatch")

    require(schema.get("$schema") == JSON_SCHEMA_DRAFT, "schema: must use Draft 2020-12")
    schema_record_types = set(schema["properties"]["record_type"]["enum"])
    schema_maturities = set(schema["properties"]["maturity"]["enum"])
    schema_dispositions = set(schema["properties"]["public_download_disposition"]["enum"])
    require(schema_record_types == RECORD_TYPES, "schema: record type enum mismatch")
    require(schema_maturities == MATURITIES, "schema: maturity enum mismatch")
    require(schema_dispositions == DISPOSITIONS, "schema: disposition enum mismatch")
    required_fields = set(adapter["required_publication_record_fields"])
    require(set(schema["required"]) == required_fields, "schema: common envelope fields mismatch")
    typed_branches = {
        branch["if"]["properties"]["record_type"]["const"]
        for branch in schema.get("allOf", [])
    }
    require(typed_branches == RECORD_TYPES, "schema: typed payload branches mismatch")


def validate_source_dispositions(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    require(document.get("schema_version") == VERSION, "source dispositions: schema version mismatch")
    require(set(document.get("disposition_enum", [])) == DISPOSITIONS, "source dispositions: enum mismatch")
    registry_inputs = document.get("registry_inputs")
    require(isinstance(registry_inputs, list) and registry_inputs, "source dispositions: registry inputs missing")
    registry_paths: set[str] = set()
    for item in registry_inputs:
        path = item.get("path")
        require(is_repository_relative(path), f"source dispositions: invalid registry path {path!r}")
        require(path not in registry_paths, f"source dispositions: duplicate registry path {path}")
        require(is_sha256(item.get("sha256")), f"source dispositions: invalid registry hash {path}")
        disk_path = REPOSITORY_ROOT / path
        require(disk_path.is_file(), f"source dispositions: missing registry input {path}")
        require(file_sha256(disk_path) == item["sha256"], f"source dispositions: stale registry hash {path}")
        registry_paths.add(path)

    entries = document.get("entries")
    require(isinstance(entries, list) and entries, "source dispositions: entries missing")
    identifiers = [item.get("source_identifier") for item in entries]
    require(identifiers == sorted(identifiers), "source dispositions: entries are not stably ordered")
    require(len(identifiers) == len(set(identifiers)), "source dispositions: duplicate source identifier")
    current_states = {"allowed", "restricted", "unknown", "not_applicable"}
    snapshot_policies = {"archived", "reference_only", "reproducible_from_git"}
    for entry in entries:
        identifier = entry["source_identifier"]
        current = entry["current_redistribution_state"]
        proposed = entry["proposed_publication_disposition"]
        require(current in current_states, f"source dispositions: unknown current state for {identifier}")
        require(proposed in DISPOSITIONS, f"source dispositions: unknown proposed state for {identifier}")
        require(entry["snapshot_policy"] in snapshot_policies, f"source dispositions: unknown snapshot policy for {identifier}")
        require(entry["repository_relative_registry_record"] in registry_paths, f"source dispositions: unknown registry for {identifier}")
        require(isinstance(entry.get("upstream_url"), str) and re.match(r"^https?://", entry["upstream_url"]), f"source dispositions: public upstream URL missing for {identifier}")
        require(bool(entry.get("rationale")), f"source dispositions: rationale missing for {identifier}")
        if current == "unknown":
            require(proposed == "blocked", f"source dispositions: unknown source must be blocked: {identifier}")
        if current == "restricted":
            require(proposed in {"excluded", "blocked"}, f"source dispositions: restricted source is unsafe: {identifier}")
        if current == "not_applicable":
            require(proposed == "public_metadata", f"source dispositions: not_applicable must be metadata-only: {identifier}")
        if entry["snapshot_policy"] == "reference_only" and current != "unknown":
            require(proposed == "reference_only", f"source dispositions: reference-only source changed disposition: {identifier}")
        if proposed == "public_body":
            require(current == "allowed", f"source dispositions: public body is not allowed: {identifier}")
            require(bool(entry.get("required_attribution_or_license_notice")), f"source dispositions: public body lacks notice: {identifier}")
        if proposed == "blocked":
            require(bool(entry.get("unresolved_question")), f"source dispositions: blocked source lacks question: {identifier}")

    computed_current = dict(sorted(Counter(item["current_redistribution_state"] for item in entries).items()))
    computed_proposed = dict(sorted(Counter(item["proposed_publication_disposition"] for item in entries).items()))
    counts = document.get("counts", {})
    require(counts.get("sources") == len(entries), "source dispositions: source count mismatch")
    require(counts.get("registry_records") == len(registry_inputs), "source dispositions: registry count mismatch")
    require(counts.get("by_current_redistribution_state") == computed_current, "source dispositions: current-state counts mismatch")
    require(counts.get("by_proposed_publication_disposition") == computed_proposed, "source dispositions: proposed-state counts mismatch")
    return {item["source_identifier"]: item for item in entries}


def deny_scan() -> tuple[int, int, dict[str, int]]:
    normative_matches = 0
    invalid_matches = 0
    candidate_matches: list[str] = []
    term_counts: Counter[str] = Counter()
    for path in sorted(PUBLICATION_ROOT.rglob("*")):
        if not path.is_file() or path.name == "__pycache__":
            continue
        relative = path.relative_to(PUBLICATION_ROOT).as_posix()
        if relative.startswith("site/"):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lower_content = content.lower()
        for key, term in DENY_SCAN_TERMS.items():
            count = lower_content.count(term.lower())
            if not count:
                continue
            term_counts[key] += count
            if relative == "fixtures/publication-record.invalid.json":
                invalid_matches += count
            elif relative == "fixtures/publication-record.valid.json":
                candidate_matches.append(f"{relative}:{key}")
            else:
                normative_matches += count
    require(not candidate_matches, "deny scan: forbidden content in valid public fixture: " + ", ".join(candidate_matches))
    return normative_matches, invalid_matches, dict(sorted(term_counts.items()))


def validate_all() -> str:
    json_paths = sorted(PUBLICATION_ROOT / relative for relative in EXPECTED_JSON_FILES)
    relative_json_paths = {path.relative_to(PUBLICATION_ROOT).as_posix() for path in json_paths}
    require(relative_json_paths == EXPECTED_JSON_FILES, "unexpected or missing contract JSON files")
    documents: dict[str, Any] = {}
    for path in json_paths:
        relative = path.relative_to(PUBLICATION_ROOT).as_posix()
        document = load_json(path)
        require(isinstance(document, dict), f"{relative}: top level must be an object")
        require(document.get("schema_version") == VERSION, f"{relative}: schema version mismatch")
        require(path.read_text(encoding="utf-8") == canonical_json(document), f"{relative}: JSON serialization is not stable")
        documents[relative] = document

    routes = documents["contract/routes.json"]
    labels = documents["contract/labels.json"]
    adapter = documents["contract/adapter-boundary.json"]
    source_dispositions = documents["contract/source-dispositions.json"]
    schema = documents["schemas/publication-record.schema.json"]
    valid_fixture = documents["fixtures/publication-record.valid.json"]
    invalid_fixture = documents["fixtures/publication-record.invalid.json"]

    validate_routes_labels_adapter(routes, labels, adapter, schema)
    source_map = validate_source_dispositions(source_dispositions)
    require(source_map, "source dispositions: empty lookup")

    valid_codes, valid_details = validate_record(
        valid_fixture, schema, routes, labels, adapter, source_dispositions
    )
    require(not valid_codes, "valid fixture failed: " + ", ".join(sorted(valid_codes)) + ("; " + "; ".join(valid_details[:5]) if valid_details else ""))
    invalid_codes, _ = validate_record(
        invalid_fixture, schema, routes, labels, adapter, source_dispositions
    )
    require(EXPECTED_INVALID_CODES <= invalid_codes, "invalid fixture did not fail for every expected reason: " + ", ".join(sorted(EXPECTED_INVALID_CODES - invalid_codes)))

    normative_matches, invalid_matches, deny_counts = deny_scan()
    counts = source_dispositions["counts"]
    current_counts = counts["by_current_redistribution_state"]
    proposed_counts = counts["by_proposed_publication_disposition"]
    lines = [
        f"publication contract valid: schema_version={VERSION} release_state={routes['release_state']}",
        f"routes={len(routes['route_families'])} labels={len(labels['labels'])} record_types={len(RECORD_TYPES)}",
        f"source_dispositions={counts['sources']} registry_records={counts['registry_records']}",
        "redistribution=" + ",".join(f"{key}:{current_counts[key]}" for key in sorted(current_counts)),
        "publication_dispositions=" + ",".join(f"{key}:{proposed_counts[key]}" for key in sorted(proposed_counts)),
        "fixtures=valid:pass invalid:expected_fail[" + ",".join(sorted(EXPECTED_INVALID_CODES)) + "]",
        f"deny_scan=public_fixture_matches:0 normative_policy_matches:{normative_matches} expected_invalid_matches:{invalid_matches}",
        "deny_terms=" + ",".join(f"{key}:{deny_counts.get(key, 0)}" for key in sorted(DENY_SCAN_TERMS)),
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional explicit temporary path for a copy of the factual summary.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = validate_all()
    if args.output is not None:
        output = args.output.resolve()
        temporary_root = Path(tempfile.gettempdir()).resolve()
        require(output.is_relative_to(temporary_root), "--output must be beneath the system temporary directory")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(summary, encoding="utf-8")
    sys.stdout.write(summary)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        raise SystemExit(f"contract validation error: {error}") from error
