#!/usr/bin/env python3
"""Regression checks for the append-only Task 08 adapter; no assessors are launched."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import reevaluate as adapter


class ReevaluationTests(unittest.TestCase):
    def test_immutable_write_allows_resume_but_never_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "assessment.yaml"
            adapter.immutable_write(path, b"original\n")
            adapter.immutable_write(path, b"original\n")
            with self.assertRaises(ValueError):
                adapter.immutable_write(path, b"replacement\n")
            self.assertEqual(path.read_bytes(), b"original\n")

    def test_selected_cohort_requires_pinned_source_and_complete_review(self):
        cohort = adapter.prep.load_yaml(adapter.TASK / "inputs/hegota-pfi-2026-08-26.yaml")
        review = adapter.prep.load_yaml(adapter.TASK / "outputs/cohort-review.yaml")
        snapshot = "hegota-test-selected"
        cohort["snapshot_id"] = review["snapshot_id"] = snapshot
        cohort["inventory"] = cohort["inventory"][:1]
        cohort["inventory"][0]["snapshot_status"] = "PFI"
        review["entries"] = review["entries"][:1]
        with tempfile.TemporaryDirectory(dir=adapter.TASK) as directory, patch.object(adapter, "TASK", Path(directory)):
            batch = adapter.configure(snapshot)
            batch.mkdir(parents=True)
            (batch / "cohort.yaml").write_bytes(adapter.prep.yaml_bytes(cohort))
            review["cohort_manifest"] = {"path": adapter.prep.rel(batch / "cohort.yaml"), "content_sha256": adapter.prep.file_sha256(batch / "cohort.yaml")}
            (batch / "review.yaml").write_bytes(adapter.prep.yaml_bytes(review))
            self.assertEqual(len(adapter.prep.approved_entries()[2]), 1)
            for key, value in (("repository_commit", "master"), ("repository", "example/other")):
                invalid = copy.deepcopy(cohort)
                invalid["source"][key] = value
                (batch / "cohort.yaml").write_bytes(adapter.prep.yaml_bytes(invalid))
                with self.assertRaises(ValueError):
                    adapter.prep.approved_entries()
            (batch / "cohort.yaml").write_bytes(adapter.prep.yaml_bytes(cohort))
            review["entries"][0]["review"]["status"] = "pending"
            (batch / "review.yaml").write_bytes(adapter.prep.yaml_bytes(review))
            with self.assertRaises(ValueError):
                adapter.prep.approved_entries()

    def test_snapshot_cannot_target_original_tree(self):
        for value in ("../outputs", "hegota/snapshot", "/tmp/batch", ""):
            with self.assertRaises(ValueError):
                adapter.configure(value)

    def test_launcher_resolves_shared_engine_without_importing_itself(self):
        launcher = adapter.module("run_isolated", "_test_reevaluation_launcher")
        self.assertEqual(Path(launcher.engine.__file__).parent, adapter.prep.TASK05_ROOT / "scripts")
        self.assertTrue(callable(launcher.engine.stage_capsule))
        self.assertTrue(callable(launcher.engine.import_output))


if __name__ == "__main__":
    unittest.main()
