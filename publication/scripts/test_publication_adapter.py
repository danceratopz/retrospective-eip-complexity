#!/usr/bin/env python3
"""Unit and integration tests for the publication adapter's data transformations.

Run from the repository root with the locked Task 05 environment:

    uv run --project research/tasks/05-retrospective-complexity-assignment --locked \
        python -m unittest publication/scripts/test_publication_adapter.py
"""

from __future__ import annotations

import json
import sys
import unittest
import copy
import tempfile
from unittest.mock import patch

import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from publication_adapter.aggregates import composition, eip_index  # noqa: E402
from publication_adapter.charts import least_squares  # noqa: E402
from publication_adapter.common import (  # noqa: E402
    PUBLIC,
    SOURCE_HUMAN,
    SOURCE_LLM,
    STATUS_AVAILABLE_IN_OPEN_PR,
    STATUS_COMPLETE,
    STATUS_INCOMPLETE,
    STATUS_IN_PROGRESS,
    STATUS_NOT_APPLICABLE,
    STATUS_NOT_AVAILABLE,
    BuildError,
    Sanitizer,
)
from publication_adapter.comparisons import agreement_class, build_comparisons  # noqa: E402
from publication_adapter.model import evaluation_date, human_assessment_from_task09, validate_scores  # noqa: E402
from publication_adapter.rubric import REGISTRY_ORDER, REVISION_1_ORDER, REVISION_2_ORDER, tier_for  # noqa: E402


def _assessment(fork: str, eip: int, source: str, revision: int, scores: dict[str, int], role: str | None = None) -> dict:
    order = REVISION_1_ORDER if revision == 1 else REVISION_2_ORDER
    criteria = [{"id": item, "score": scores.get(item, 0)} for item in order]
    total = sum(item["score"] for item in criteria)
    return {
        "id": f"{fork}:{eip}:{source}:r{revision}",
        "eip": eip,
        "fork": fork,
        "source": source,
        "rubric_revision": revision,
        "role": role or ("primary" if source == SOURCE_LLM else "published_checklist"),
        "scored": True,
        "score": total,
        "tier": tier_for(total, revision),
        "criteria": criteria,
    }


class EvaluationHistoryTests(unittest.TestCase):
    def test_dates_preserve_recorded_precision_and_normalize_offsets(self):
        self.assertEqual(evaluation_date("2026-09-11T00:30:00+02:00"), "2026-09-10")
        self.assertEqual(evaluation_date("2026-08-26"), "2026-08-26")
        self.assertIsNone(evaluation_date(None))
        for bad in ("yesterday", "2026-09-11T00:00:00", "2026-02-30"):
            with self.assertRaises(BuildError):
                evaluation_date(bad)

    def test_append_history_preserves_originals_and_rejects_invalid_entries(self):
        from publication_adapter import history
        from publication_adapter.common import ROOT, TASK08, digest, load_json, load_yaml, relative
        from publication_adapter.sources import load_prospective
        from publication_adapter.aggregates import fork_summaries
        occurrences, originals, _, _ = load_prospective()
        before = copy.deepcopy(originals)
        candidates = {item["eip"] for item in occurrences}
        registry = load_yaml(TASK08 / "outputs/evaluation-registry.yaml")
        boundary = load_json(history.CONTRACT / "adapter-boundary.json")
        with tempfile.TemporaryDirectory(dir=TASK08) as temporary:
            base = Path(temporary)
            snapshot = "hegota-test-repeat"
            batch = base / snapshot
            (batch / "assessments").mkdir(parents=True)
            entry = copy.deepcopy(registry["evaluations"][0])
            original_id = entry["id"]
            record = load_yaml(ROOT / entry["assessment_path"])
            record["snapshot_id"] = snapshot
            record["provenance"]["cohort_snapshot"]["snapshot_id"] = snapshot
            record["provenance"]["assessor"]["run_at"] = "2026-09-16T09:00:00Z"
            path = batch / "assessments" / f"eip-{entry['eip']}.yaml"
            path.write_text(yaml.safe_dump(record))
            entry.update(id=original_id + ":" + snapshot, snapshot_id=snapshot,
                         assessment_path=relative(path), assessment_sha256=digest(path))
            freeze_path = batch / "assessment-manifest.yaml"
            freeze_path.write_text(yaml.safe_dump({"snapshot_id": snapshot, "assessment_count": 1, "assessments": [dict(entry)]}))
            report = batch / "validation-report.yaml"
            report.write_text(yaml.safe_dump({"snapshot_id": snapshot, "result": "pass", "assessment_freeze_sha256": digest(freeze_path)}))
            entry.update(freeze_path=relative(freeze_path), freeze_sha256=digest(freeze_path),
                         validation_path=relative(report), validation_sha256=digest(report))
            registry["evaluations"].append(entry)
            registry_path = base / "registry.yaml"
            boundary["evaluation_history"].update(registry=relative(registry_path), assessment_root=relative(base))
            with patch.object(history, "load_json", return_value=boundary):
                registry_path.write_text(yaml.safe_dump(registry))
                additions, _ = history.load_history(originals, candidates)
                self.assertEqual(len(additions), 1)
                self.assertEqual(additions[0]["id"], entry["id"])
                self.assertEqual(additions[0]["evaluation_date"], "2026-09-16")
                self.assertEqual(originals, before)
                assessment_map = {item["id"]: item for item in originals + additions}
                for occurrence in occurrences:
                    occurrence["human"] = {"status": "not_available", "assessment_id": None}
                totals = fork_summaries(occurrences, assessment_map)
                self.assertEqual(next(item for item in totals if item["fork"] == "hegota")["score_sum"], 856)
                for mutate in (
                    lambda r: r["evaluations"].append(copy.deepcopy(entry)),
                    lambda r: r["evaluations"].pop(0),
                    lambda r: r["evaluations"][-1].update(assessment_sha256="0" * 64),
                    lambda r: r["evaluations"][-1].update(id=original_id),
                    lambda r: r["evaluations"][-1].update(assessment_path="/etc/passwd"),
                ):
                    broken = copy.deepcopy(registry)
                    mutate(broken)
                    registry_path.write_text(yaml.safe_dump(broken))
                    with self.assertRaises(BuildError):
                        history.load_history(originals, candidates)


class RubricTests(unittest.TestCase):
    def test_registry_covers_both_revisions_once(self) -> None:
        self.assertEqual(len(REGISTRY_ORDER), 29)
        self.assertEqual(set(REGISTRY_ORDER), set(REVISION_1_ORDER) | set(REVISION_2_ORDER))
        self.assertEqual(len(REVISION_1_ORDER), 24)
        self.assertEqual(len(REVISION_2_ORDER), 28)

    def test_tier_thresholds(self) -> None:
        self.assertEqual([tier_for(value, 2) for value in (0, 11, 12, 22, 23, 90)], ["low", "low", "medium", "medium", "high", "high"])
        self.assertEqual([tier_for(value, 1) for value in (0, 9, 10, 19, 20)], ["low", "low", "medium", "medium", "high"])

    def test_validate_scores_rejects_inconsistent_totals(self) -> None:
        criteria = [{"id": item, "score": 0} for item in REVISION_2_ORDER]
        criteria[0]["score"] = 3
        with self.assertRaises(BuildError):
            validate_scores(criteria, 4, "low", 2, "test")
        with self.assertRaises(BuildError):
            validate_scores(criteria, 3, "medium", 2, "test")
        validate_scores(criteria, 3, "low", 2, "test")


class FitTests(unittest.TestCase):
    def test_exact_line_has_zero_residual_and_band(self) -> None:
        rows = [{"total_score": x, "shipping_days": 100 + 2 * x} for x in (10, 20, 30, 40, 50)]
        fit = least_squares(rows, 100)
        self.assertEqual((fit["slope_days_per_point"], fit["intercept_days"], fit["r_squared"]), (2.0, 100.0, 1.0))
        self.assertTrue(all(point[f"lower_{level}"] == point["fit"] == point[f"upper_{level}"] for point in fit["band"] for level in (50, 80, 95)))

    def test_band_widens_away_from_the_mean(self) -> None:
        rows = [{"total_score": x, "shipping_days": y} for x, y in ((65, 124), (126, 415), (216, 355), (105, 191), (243, 405))]
        band = least_squares(rows, 600)["band"]
        width = [point["upper_95"] - point["lower_95"] for point in band]
        self.assertTrue(all(p["lower_95"] <= p["lower_80"] <= p["lower_50"] <= p["fit"] <= p["upper_50"] <= p["upper_80"] <= p["upper_95"] for p in band))
        middle = min(range(len(width)), key=width.__getitem__)
        self.assertTrue(0 < middle < len(width) - 1)
        self.assertGreater(width[-1], width[middle])


class ComparisonTests(unittest.TestCase):
    def test_agreement_classes(self) -> None:
        self.assertEqual([agreement_class(value) for value in (0, 1, -1, 2, -3)], ["exact", "minor", "minor", "major", "major"])

    def test_human_pairs_with_primary_llm_across_revisions(self) -> None:
        human = _assessment("amsterdam", 1, SOURCE_HUMAN, 1, {"security_risks": 3, "cross_eip_interactions": 1, "engine_api_encoding_changes": 2})
        primary = _assessment("amsterdam", 1, SOURCE_LLM, 3, {"security_risks": 3, "cross_eip_interactions": 3, "new_invariant_on_pre_existing_tests": 2})
        rerun = _assessment("amsterdam", 1, SOURCE_LLM, 1, {"security_risks": 1}, role="historical_rubric_rerun")
        comparisons = build_comparisons({item["id"]: item for item in (human, primary, rerun)}, {})
        self.assertEqual(list(comparisons), ["amsterdam:1:human-r1:llm-r3"])
        comparison = comparisons["amsterdam:1:human-r1:llm-r3"]
        self.assertEqual(comparison["llm_assessment_id"], primary["id"])
        self.assertEqual((comparison["human_rubric_revision"], comparison["llm_rubric_revision"], comparison["same_revision"]), (1, 3, False))
        self.assertEqual(comparison["delta"], primary["score"] - human["score"])
        self.assertEqual(comparison["largest_disagreements"], ["cross_eip_interactions"])
        rows = {row["id"]: row for row in comparison["rows"]}
        self.assertEqual((rows["cross_eip_interactions"]["delta"], rows["cross_eip_interactions"]["agreement"]), (2, "major"))
        # Criteria in only one revision carry scores but no difference.
        self.assertEqual((rows["engine_api_encoding_changes"]["human"], rows["engine_api_encoding_changes"]["delta"]), (2, None))
        self.assertEqual((rows["new_invariant_on_pre_existing_tests"]["llm"], rows["new_invariant_on_pre_existing_tests"]["shared"]), (2, False))
        self.assertEqual(sum(comparison["agreement_counts"].values()), 23)

    def test_only_the_primary_llm_assessment_is_compared(self):
        human = _assessment("hegota", 8272, SOURCE_HUMAN, 2, {})
        reevaluation = _assessment("hegota", 8272, SOURCE_LLM, 2, {"security_risks": 3}, role="reevaluation")
        self.assertEqual(build_comparisons({a["id"]: a for a in (reevaluation, human)}, {}), {})

    def test_unscored_assessments_are_never_compared(self) -> None:
        human = _assessment("hegota", 1, SOURCE_HUMAN, 2, {})
        human["scored"] = False
        llm = _assessment("hegota", 1, SOURCE_LLM, 2, {"security_risks": 2})
        self.assertEqual(build_comparisons({human["id"]: human, llm["id"]: llm}, {}), {})


class AggregateTests(unittest.TestCase):
    def test_composition_sums_every_criterion(self) -> None:
        first = _assessment("prague", 1, SOURCE_LLM, 2, {"security_risks": 3, "added_opcodes": 2})
        second = _assessment("prague", 2, SOURCE_LLM, 2, {"security_risks": 1})
        result = composition([first, second])
        by_id = {item["id"]: item for item in result["criteria"]}
        self.assertEqual(result["score_sum"], 6)
        self.assertEqual(by_id["security_risks"], {"id": "security_risks", "score_sum": 4, "eip_count": 2})
        self.assertEqual(by_id["added_opcodes"], {"id": "added_opcodes", "score_sum": 2, "eip_count": 1})
        self.assertEqual([item["id"] for item in result["criteria"]], [item for item in REGISTRY_ORDER if item in REVISION_2_ORDER])

    def test_default_fork_prefers_latest_retrospective_occurrence(self) -> None:
        occurrences = [
            {"eip": 7642, "title": "eth/69", "fork": "osaka", "mode": "retrospective", "snapshot_status": None},
            {"eip": 7642, "title": "eth/69", "fork": "prague", "mode": "retrospective", "snapshot_status": None},
            {"eip": 7805, "title": "FOCIL", "fork": "hegota", "mode": "prospective", "snapshot_status": "SFI"},
        ]
        eips = eip_index(occurrences)
        self.assertEqual([(item["eip"], item["forks"], item["default_fork"]) for item in eips], [(7642, ["prague", "osaka"], "osaka"), (7805, ["hegota"], "hegota")])


class HumanCandidateTests(unittest.TestCase):
    RUBRICS = {2: {"repository": "ethspecs/pm", "commit": "abc", "path": "Templates/EIP-Complexity-Assessment.md", "immutable_url": "https://example.invalid"}}

    def _candidate(self, parse_state: str, availability: str, total: int | None) -> dict:
        scores = [
            {"id": item, "raw_score_cell": "0", "parsed_terms": [0], "numeric_contribution": 0, "rationale": "", "blank_interpretation": None}
            for item in REVISION_2_ORDER
        ]
        scores[0]["raw_score_cell"] = "3"
        scores[0]["numeric_contribution"] = 3
        return {
            "candidate_id": "pr-1@abc",
            "availability": availability,
            "parse_state": parse_state,
            "rubric_revision": 2,
            "scores": scores,
            "published_total": total,
            "published_tier": "low",
            "recomputed_total": 3,
            "recomputed_tier": "low",
            "parser_notes": [],
            "source": {
                "kind": "open_pull_request",
                "repository": "ethspecs/pm",
                "pull_request": 1,
                "pull_request_title": "Add assessment",
                "pull_request_url": "https://github.com/ethspecs/pm/pull/1",
                "draft": availability == "open_draft_pull_request",
                "head_sha": "abc",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
                "path": "complexity_assessments/EIPs/EIP-1.md",
                "git_blob_sha": "def",
                "content_sha256": "0" * 64,
                "immutable_url": "https://github.com/ethspecs/pm/blob/abc/complexity_assessments/EIPs/EIP-1.md",
            },
        }

    def test_complete_pull_request_candidate_is_scored(self) -> None:
        assessment = human_assessment_from_task09(
            self._candidate("complete", "open_pull_request", 3), eip=1, title="Test", status=STATUS_AVAILABLE_IN_OPEN_PR, path=Path(__file__), rubric_sources=self.RUBRICS
        )
        self.assertTrue(assessment["scored"])
        self.assertEqual((assessment["score"], assessment["tier"], assessment["status"]), (3, "low", STATUS_AVAILABLE_IN_OPEN_PR))
        self.assertEqual(assessment["provenance"]["source_record"]["pull_request"]["number"], 1)

    def test_incomplete_candidate_never_receives_a_score(self) -> None:
        assessment = human_assessment_from_task09(
            self._candidate("incomplete", "open_draft_pull_request", None), eip=1, title="Test", status=STATUS_IN_PROGRESS, path=Path(__file__), rubric_sources=self.RUBRICS
        )
        self.assertFalse(assessment["scored"])
        self.assertIsNone(assessment["score"])
        self.assertIsNone(assessment["tier"])
        self.assertEqual(assessment["provenance"]["source_record"]["kind"], "open_draft_pull_request")


class SanitizerTests(unittest.TestCase):
    def test_forbidden_keys_and_values(self) -> None:
        sanitizer = Sanitizer()
        with self.assertRaises(BuildError):
            sanitizer.check({"session_id": "x"})
        with self.assertRaises(BuildError):
            sanitizer.check({"note": "see /home/someone/file"})
        with self.assertRaises(BuildError):
            sanitizer.check({"run": "assessment-run-0123abcd"})
        sanitizer.check({"path": "research/tasks/05/outputs/x.yaml", "url": "https://github.com/x"})


@unittest.skipUnless((PUBLIC / "publication.json").is_file(), "publication.json has not been generated")
class GeneratedPayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads((PUBLIC / "publication.json").read_text(encoding="utf-8"))
        cls.index = json.loads((PUBLIC / "compare-index.json").read_text(encoding="utf-8"))
        cls.occurrences = [occurrence for eip in cls.data["eips"] for occurrence in eip["occurrences"]]

    def test_population_counts(self) -> None:
        self.assertEqual(len(self.occurrences), 84)
        self.assertEqual(len(self.data["eips"]), 83)
        retrospective = [item for item in self.occurrences if item["mode"] == "retrospective"]
        prospective = [item for item in self.occurrences if item["mode"] == "prospective"]
        self.assertEqual((len(retrospective), len(prospective)), (49, 35))
        self.assertEqual(sum(1 for item in prospective if item["llm"]["status"] == STATUS_NOT_APPLICABLE), 8)
        llm = [item for item in self.data["assessments"].values() if item["source"] == "llm"]
        self.assertTrue(all(item["provenance"]["assessor"]["model"] == "claude-opus-5-5" and item["rubric_revision"] == 3 for item in llm))

    def test_totals_match_source_gates(self) -> None:
        forks = {item["fork"]: item for item in self.data["forks"]}
        self.assertEqual({fork: forks[fork]["at_cutoff_score_sum"] for fork in ("shanghai", "cancun", "prague", "osaka", "amsterdam")}, {"shanghai": 58, "cancun": 109, "prague": 159, "osaka": 72, "amsterdam": 238})
        self.assertEqual(list(self.data["fork_shipping"]["evaluations"]), ["opus-v3"])
        builder = self.data["hegota_builder"]
        self.assertEqual({name: item["score_sum"] for name, item in builder["scenarios"].items()}, {"SFI": 77, "SFI+CFI": 273, "SFI+CFI+PFI": 543})
        self.assertTrue(all(item["score"] is None for item in builder["entries"] if item["status"] == STATUS_NOT_APPLICABLE))
        self.assertEqual(forks["hegota"]["score_sum"], 543)
        for fork in forks.values():
            for name, block in fork["composition"].items():
                self.assertEqual(sum(item["score_sum"] for item in block["criteria"]), block["score_sum"], f"{fork['fork']} {name}")
            if fork["mode"] == "retrospective":
                self.assertEqual(fork["composition"]["at_cutoff"]["score_sum"], fork["at_cutoff_score_sum"])
                self.assertEqual(fork["composition"]["final_scope"]["score_sum"], fork["final_scope_score_sum"])

    def test_every_assessment_is_internally_consistent(self) -> None:
        for assessment in self.data["assessments"].values():
            order = self.data["rubrics"][str(assessment["rubric_revision"])]["criteria"]
            self.assertEqual([item["id"] for item in assessment["criteria"]], order, assessment["id"])
            if assessment["scored"]:
                self.assertEqual(sum(item["score"] for item in assessment["criteria"]), assessment["score"], assessment["id"])
                self.assertEqual(tier_for(assessment["score"], assessment["rubric_revision"]), assessment["tier"], assessment["id"])
            else:
                self.assertIsNone(assessment["score"], assessment["id"])
                self.assertIsNone(assessment["tier"], assessment["id"])

    def test_missing_human_assessments_are_not_zero(self) -> None:
        statuses = {}
        for occurrence in self.occurrences:
            human = occurrence["human"]
            statuses[human["status"]] = statuses.get(human["status"], 0) + 1
            if human["assessment_id"] is None:
                self.assertIsNone(human["score"], occurrence["id"])
                self.assertIn(human["status"], {STATUS_NOT_AVAILABLE})
            else:
                assessment = self.data["assessments"][human["assessment_id"]]
                self.assertEqual(assessment["source"], SOURCE_HUMAN)
                self.assertEqual(assessment["status"], human["status"])
        hegota = [item["human"]["status"] for item in self.occurrences if item["fork"] == "hegota"]
        self.assertEqual(
            {status: hegota.count(status) for status in set(hegota)},
            {STATUS_COMPLETE: 2, STATUS_AVAILABLE_IN_OPEN_PR: 8, STATUS_IN_PROGRESS: 5, STATUS_NOT_AVAILABLE: 20},
        )
        self.assertEqual(sum(1 for item in self.occurrences if item["fork"] == "amsterdam" and item["human"]["status"] == STATUS_COMPLETE), 12)
        cell_sum_rule = self.data["assessments"]["hegota:8250:human:r2"]
        self.assertTrue(cell_sum_rule["scored"])
        self.assertEqual((cell_sum_rule["score"], cell_sum_rule["checklist"]["published_total"]), (22, 20))

    def test_comparisons_pair_humans_with_opus_and_are_reproducible(self) -> None:
        for comparison in self.data["comparisons"].values():
            human = self.data["assessments"][comparison["human_assessment_id"]]
            llm = self.data["assessments"][comparison["llm_assessment_id"]]
            self.assertEqual((llm["role"], llm["rubric_revision"]), ("primary", 3))
            self.assertEqual(human["rubric_revision"], comparison["human_rubric_revision"])
            self.assertEqual(comparison["delta"], llm["score"] - human["score"])
            for row in comparison["rows"]:
                if row["shared"]:
                    self.assertEqual(row["delta"], row["llm"] - row["human"])
        amsterdam = [item for item in self.data["comparisons"].values() if item["fork"] == "amsterdam"]
        self.assertEqual(len(amsterdam), 12)
        by_eip = {item["eip"]: item for item in amsterdam}
        self.assertEqual((by_eip[7928]["human_total"], by_eip[7928]["llm_total"]), (29, 41))

    def test_human_llm_alignment_summary(self) -> None:
        alignment = self.data["human_llm"]
        self.assertEqual((alignment["summary"]["comparison_count"], alignment["shared_criteria"]), (12, 23))
        self.assertEqual([row["eip"] for row in alignment["rows"][:3]], [7928, 8037, 8038])
        self.assertEqual((alignment["summary"]["mean_absolute_delta"], alignment["summary"]["mean_signed_delta"]), (7.5833, 6.5833))
        by_id = {item["id"]: item for item in alignment["criteria"]}
        self.assertEqual(by_id["security_risks"]["mean_delta"], 0.6667)
        self.assertEqual(by_id["evm_gas_rule_changes"]["mean_delta"], -1.0833)
        self.assertEqual(alignment["summary"]["tier_agreement_count"], 7)

    def test_compare_index_mirrors_assessments(self) -> None:
        self.assertEqual([item["id"] for item in self.index["criteria"]], REGISTRY_ORDER)
        rows = {item["id"]: item for item in self.index["assessments"]}
        self.assertEqual(set(rows), set(self.data["assessments"]))
        for identifier, row in rows.items():
            assessment = self.data["assessments"][identifier]
            scores = {item["id"]: item["score"] for item in assessment["criteria"]}
            self.assertEqual(row["scores"], [scores.get(criterion) for criterion in REGISTRY_ORDER])


if __name__ == "__main__":
    unittest.main()
