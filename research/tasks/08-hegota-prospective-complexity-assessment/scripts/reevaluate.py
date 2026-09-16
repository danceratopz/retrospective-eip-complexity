#!/usr/bin/env python3
"""Prepare, validate, run, and register immutable selected-cohort re-evaluations."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import tempfile
from pathlib import Path

# Load Task 08 modules by path: the shared engine also has identically named scripts.
SCRIPTS = Path(__file__).resolve().parent


def module(name, alias=None):
    import_name = alias or name
    spec = importlib.util.spec_from_file_location(import_name, SCRIPTS / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    sys.modules[import_name] = result
    spec.loader.exec_module(result)
    return result


prep = module("prepare_packages")
packages = module("validate_packages")
outputs = module("validate_assessment")
cohorts = module("validate_cohort")
TASK = prep.TASK_ROOT


def immutable_write(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Refusing to replace frozen content: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def configure(snapshot):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", snapshot):
        raise ValueError("Snapshot ID must contain lowercase letters, digits, and hyphens")
    batch = TASK / "evaluations" / snapshot
    if not batch.resolve().is_relative_to((TASK / "evaluations").resolve()):
        raise ValueError("Batch escapes evaluation root")
    for path in batch.rglob("*"):
        if path.is_symlink():
            raise ValueError("Evaluation batches must not contain symlinks")
    for target in (prep, packages):
        target.COHORT_PATH = batch / "cohort.yaml"
        target.REVIEW_PATH = batch / "review.yaml"
        target.PACKAGE_ROOT = batch / "packages"
        target.PROMPT_ROOT = batch / "prompts"
        target.PACKAGE_FREEZE = batch / "package-manifest.yaml"
        target.TASK_CONTRACT = TASK / "REEVALUATION.md"
    packages.EXPECTED_SNAPSHOT_ID = snapshot
    outputs.EXPECTED_SNAPSHOT_ID = snapshot
    outputs.PACKAGE_ROOT = prep.PACKAGE_ROOT
    outputs.PROMPT_ROOT = prep.PROMPT_ROOT
    outputs.OUTPUT_ROOT = batch / "assessments"
    outputs.RAW_ROOT = batch / "raw"

    def approved_entries():
        cohort = prep.load_yaml(prep.COHORT_PATH)
        review = prep.load_yaml(prep.REVIEW_PATH)
        inventory, entries = cohort["inventory"], review["entries"]
        numbers = [item["eip"] for item in inventory]
        if cohort["snapshot_id"] != snapshot or review["snapshot_id"] != snapshot:
            raise ValueError("Snapshot identity mismatch")
        expected_review_source = {"path": prep.rel(prep.COHORT_PATH), "content_sha256": prep.file_sha256(prep.COHORT_PATH)}
        if review.get("cohort_manifest") != expected_review_source or review.get("proposal_source") != {"repository": "ethereum/EIPs", "repository_commit": cohort["source"]["repository_commit"]}:
            raise ValueError("Applicability review must identify this exact cohort manifest and commit")
        if not numbers or len(set(numbers)) != len(numbers) or numbers != [item["eip"] for item in entries]:
            raise ValueError("Review must cover the exact nonempty selected inventory")
        if review["review_gate"]["status"] != "approved" or any(item["review"]["status"] != "approved" for item in entries):
            raise ValueError("Every selected proposal needs approved applicability review")
        if not re.fullmatch(r"[0-9a-f]{40}", cohort["source"]["repository_commit"]):
            raise ValueError("Pin a full EIPs commit before preparation")
        if cohort["source"]["repository"] != "ethereum/EIPs":
            raise ValueError("Expected ethereum/EIPs source")
        for item, entry in zip(inventory, entries):
            if item["path"] != f"EIPS/eip-{item['eip']}.md" or item.get("snapshot_status") not in {"PFI", "CFI", "SFI"}:
                raise ValueError("Invalid EIP path or snapshot inclusion status")
            if entry["disposition"] not in {"score_el_rubric", "not_applicable_to_el_rubric"}:
                raise ValueError("Unknown applicability disposition")
            if entry["disposition"] == "score_el_rubric" and "execution" not in entry["affected_layers"]:
                raise ValueError("Consensus-only proposal cannot receive an EL score")
        return cohort, review, [item for item in entries if item["disposition"] == "score_el_rubric"]

    prep.approved_entries = approved_entries
    original_prompt = prep.render_prompt
    prep.render_prompt = lambda number, title: original_prompt(number, title).replace(b"Hegot\xc3\xa1 PFI snapshot", b"Hegot\xc3\xa1 selected-cohort snapshot")
    return batch


def verify_source(eips_repo):
    cohort, _, _ = prep.approved_entries()
    source = cohort["source"]
    if source["path"] != "EIPS/eip-8081.md":
        raise ValueError("Expected Hegotá meta EIP source")
    data, blob = prep.git_blob(eips_repo, source["repository_commit"], source["path"])
    if blob != source["git_blob_sha"] or prep.sha256(data) != source["content_sha256"]:
        raise ValueError("Meta EIP source hash mismatch")
    members = {}
    for status, heading in [("PFI", "Proposed for Inclusion"), ("CFI", "Considered for Inclusion"), ("SFI", "EIPs Scheduled for Inclusion")]:
        for number, _ in cohorts.section_items(data.decode(), heading):
            if number in members:
                raise ValueError("Meta EIP contains duplicate membership")
            members[number] = status
    for item in cohort["inventory"]:
        if members.get(item["eip"]) != item["snapshot_status"]:
            raise ValueError(f"Inclusion status differs from pinned meta EIP: {item['eip']}")


def verify_freeze():
    cohort, _, _ = prep.approved_entries()
    packages.EXPECTED_COMMIT = cohort["source"]["repository_commit"]
    packages.validate_inventory()
    adapter = {"path": prep.rel(Path(__file__).resolve()), "sha256": prep.file_sha256(Path(__file__).resolve())}
    for item in prep.approved_entries()[2]:
        manifest = prep.load_yaml(prep.PACKAGE_ROOT / f"eip-{item['eip']}" / "manifest.yaml")
        if manifest["preparation"].get("reevaluation_adapter") != adapter:
            raise ValueError("Re-evaluation adapter differs from sealed preparation provenance")
    if prep.PACKAGE_FREEZE.read_bytes() != prep.yaml_bytes(prep.package_inventory()):
        raise ValueError("Package freeze no longer matches the batch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--eip", type=int)
    parser.add_argument("--eips-repo", type=Path, default=prep.package_engine.repo_default("EIPs"))
    parser.add_argument("--pm-repo", type=Path, default=prep.package_engine.repo_default("pm"))
    parser.add_argument("--external-repo", action="append", default=[])
    parser.add_argument("action", choices=["prepare", "verify-regeneration", "run", "validate", "freeze", "register"])
    args = parser.parse_args()
    batch = configure(args.snapshot)
    if args.action in {"prepare", "verify-regeneration"}:
        verify_source(args.eips_repo)
        with tempfile.TemporaryDirectory(prefix="hegota-reevaluation-") as temporary:
            stage = Path(temporary)
            prep.build_packages(target_package_root=stage / "packages", target_prompt_root=stage / "prompts",
                                eips_repo=args.eips_repo, pm_repo=args.pm_repo,
                                external_repos=prep.external_repo_map(args.external_repo), write_common_rubric=False)
            for package in (stage / "packages").glob("eip-*"):
                manifest_path = package / "manifest.yaml"
                manifest = prep.load_yaml(manifest_path)
                manifest["preparation"]["reevaluation_adapter"] = {"path": prep.rel(Path(__file__).resolve()), "sha256": prep.file_sha256(Path(__file__).resolve())}
                manifest_path.write_bytes(prep.yaml_bytes(manifest))
                template_path = package / "output-template.yaml"
                template = prep.load_yaml(template_path)
                template["provenance"]["input_package"]["manifest_sha256"] = prep.file_sha256(manifest_path)
                template_path.write_bytes(prep.yaml_bytes(template))
            for name in ("packages", "prompts"):
                target = batch / name
                if args.action == "prepare":
                    # Check the whole tree before writing anything; interrupted preparation can resume.
                    for path in sorted((stage / name).rglob("*")):
                        dest = target / path.relative_to(stage / name)
                        if path.is_file() and dest.exists() and dest.read_bytes() != path.read_bytes():
                            raise ValueError(f"Refusing to change prepared file: {dest}")
                    for path in sorted((stage / name).rglob("*")):
                        if path.is_file():
                            immutable_write(target / path.relative_to(stage / name), path.read_bytes())
                prep.compare_tree(target, stage / name)
        if args.action == "prepare":
            immutable_write(prep.PACKAGE_FREEZE, prep.yaml_bytes(prep.package_inventory()))
        verify_freeze()
        if args.action == "verify-regeneration":
            immutable_write(batch / "regeneration.yaml", prep.yaml_bytes({"snapshot_id": args.snapshot, "package_freeze_sha256": prep.file_sha256(prep.PACKAGE_FREEZE), "result": "pass"}))
        return 0
    verify_freeze()
    cohort, _, entries = prep.approved_entries()
    if args.action in {"run", "freeze", "register"}:
        receipt = prep.load_yaml(batch / "regeneration.yaml")
        if receipt != {"snapshot_id": args.snapshot, "package_freeze_sha256": prep.file_sha256(prep.PACKAGE_FREEZE), "result": "pass"}:
            raise ValueError("Batch needs successful deterministic regeneration before running or freezing")
    if args.action == "run":
        if args.eip not in [item["eip"] for item in entries]:
            raise ValueError("Choose a scorable EIP from this batch")
        launcher = module("run_isolated", "_reevaluation_launcher")
        launcher.engine.LOCK_PARENT = Path("/tmp/hegota-prospective-complexity-assessment-locks") / args.snapshot
        launcher.engine.package_paths = outputs.package_paths
        launcher.engine.validate = outputs.validate
        launcher.engine.validate_package = lambda _fork, package: packages.validate_package(package)
        sys.argv = [sys.argv[0], "--fork", "hegota", "--eip", str(args.eip)]
        return launcher.main()
    rows = []
    for entry in entries:
        number = entry["eip"]
        path = outputs.validate("hegota", number)
        rows.append({"eip": number, "assessment_path": prep.rel(path), "assessment_sha256": prep.file_sha256(path)})
    freeze_path, validation_path = batch / "assessment-manifest.yaml", batch / "validation-report.yaml"
    freeze = {"schema_version": 1, "snapshot_id": args.snapshot, "assessment_count": len(rows), "assessments": rows}
    validation = {"snapshot_id": args.snapshot, "result": "pass", "assessment_count": len(rows), "assessment_freeze_sha256": prep.sha256(prep.yaml_bytes(freeze)), "package_freeze_sha256": prep.file_sha256(prep.PACKAGE_FREEZE)}
    if args.action == "validate":
        return 0
    if args.action == "freeze":
        immutable_write(freeze_path, prep.yaml_bytes(freeze))
        immutable_write(validation_path, prep.yaml_bytes(validation))
        return 0
    if prep.load_yaml(freeze_path) != freeze or prep.load_yaml(validation_path) != validation:
        raise ValueError("Batch differs from validated assessment freeze")
    registry_path = TASK / "outputs/evaluation-registry.yaml"
    registry = prep.load_yaml(registry_path)
    existing = {item["id"]: item for item in registry["evaluations"]}
    candidates = prep.load_yaml(TASK / "outputs/summary-all-candidates.yaml")
    allowed = {item["eip"] for key in ("scored_eips", "not_applicable_eips") for item in candidates[key]}
    statuses = {item["eip"]: item["snapshot_status"] for item in cohort["inventory"]}
    for row in rows:
        number = row["eip"]
        if number not in allowed:
            raise ValueError("New candidates need a membership/publication extension")
        item = dict(row, id=f"hegota:{number}:llm:r2:{args.snapshot}", snapshot_id=args.snapshot,
                    snapshot_status=statuses[number], freeze_path=prep.rel(freeze_path), freeze_sha256=prep.file_sha256(freeze_path),
                    validation_path=prep.rel(validation_path), validation_sha256=prep.file_sha256(validation_path))
        if item["id"] in existing:
            if existing[item["id"]] != item:
                raise ValueError("Refusing to change a registered evaluation")
        else:
            registry["evaluations"].append(item)
    # One atomic registry replacement, after all entries have passed validation.
    staging = registry_path.with_suffix(".yaml.tmp")
    with staging.open("x") as stream:
        stream.write(prep.yaml_bytes(registry).decode())
    staging.replace(registry_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
