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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from publication_adapter.aggregates import composition, eip_index  # noqa: E402
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
from publication_adapter.model import human_assessment_from_task09, validate_scores  # noqa: E402
from publication_adapter.rubric import REGISTRY_ORDER, REVISION_1_ORDER, REVISION_2_ORDER, tier_for  # noqa: E402


def _assessment(fork: str, eip: int, source: str, revision: int, scores: dict[str, int]) -> dict:
    order = REVISION_2_ORDER if revision == 2 else REVISION_1_ORDER
    criteria = [{"id": item, "score": scores.get(item, 0)} for item in order]
    total = sum(item["score"] for item in criteria)
    return {
        "id": f"{fork}:{eip}:{source}:r{revision}",
        "eip": eip,
        "fork": fork,
        "source": source,
        "rubric_revision": revision,
        "scored": True,
        "score": total,
        "tier": tier_for(total, revision),
        "criteria": criteria,
    }


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


class ComparisonTests(unittest.TestCase):
    def test_agreement_classes(self) -> None:
        self.assertEqual([agreement_class(value) for value in (0, 1, -1, 2, -3)], ["exact", "minor", "minor", "major", "major"])

    def test_same_rubric_pairs_only(self) -> None:
        human = _assessment("amsterdam", 1, SOURCE_HUMAN, 1, {"security_risks": 3, "cross_eip_interactions": 1})
        llm_r1 = _assessment("amsterdam", 1, SOURCE_LLM, 1, {"security_risks": 3, "cross_eip_interactions": 3})
        llm_r2 = _assessment("amsterdam", 1, SOURCE_LLM, 2, {"security_risks": 3})
        comparisons = build_comparisons({item["id"]: item for item in (human, llm_r1, llm_r2)}, {})
        self.assertEqual(list(comparisons), ["amsterdam:1:r1"])
        comparison = comparisons["amsterdam:1:r1"]
        self.assertEqual(comparison["delta"], 2)
        self.assertEqual(comparison["largest_disagreements"], ["cross_eip_interactions"])
        row = next(item for item in comparison["rows"] if item["id"] == "cross_eip_interactions")
        self.assertEqual((row["human"], row["llm"], row["delta"], row["agreement"]), (1, 3, 2, "major"))
        self.assertEqual(comparison["agreement_counts"], {"exact": 23, "minor": 0, "major": 1})

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
        self.assertEqual(len(self.occurrences), 95)
        self.assertEqual(len(self.data["eips"]), 94)
        retrospective = [item for item in self.occurrences if item["mode"] == "retrospective"]
        prospective = [item for item in self.occurrences if item["mode"] == "prospective"]
        self.assertEqual((len(retrospective), len(prospective)), (49, 46))
        self.assertEqual(sum(1 for item in prospective if item["llm"]["status"] == STATUS_NOT_APPLICABLE), 7)

    def test_totals_match_source_gates(self) -> None:
        forks = {item["fork"]: item for item in self.data["forks"]}
        self.assertEqual({fork: forks[fork]["at_cutoff_score_sum"] for fork in ("shanghai", "cancun", "prague", "osaka", "amsterdam")}, {"shanghai": 65, "cancun": 126, "prague": 216, "osaka": 105, "amsterdam": 243})
        self.assertEqual(forks["hegota"]["score_sum"], 856)
        self.assertEqual(forks["hegota"]["composition"]["pfi_only"]["score_sum"], 776)
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
            {STATUS_COMPLETE: 2, STATUS_AVAILABLE_IN_OPEN_PR: 15, STATUS_IN_PROGRESS: 8, STATUS_NOT_AVAILABLE: 21},
        )
        self.assertEqual(sum(1 for item in self.occurrences if item["fork"] == "amsterdam" and item["human"]["status"] == STATUS_COMPLETE), 12)
        cell_sum_rule = self.data["assessments"]["hegota:8250:human:r2"]
        self.assertTrue(cell_sum_rule["scored"])
        self.assertEqual((cell_sum_rule["score"], cell_sum_rule["checklist"]["published_total"]), (22, 20))

    def test_comparisons_are_same_rubric_and_reproducible(self) -> None:
        for comparison in self.data["comparisons"].values():
            human = self.data["assessments"][comparison["human_assessment_id"]]
            llm = self.data["assessments"][comparison["llm_assessment_id"]]
            self.assertEqual(human["rubric_revision"], llm["rubric_revision"])
            self.assertEqual(comparison["delta"], llm["score"] - human["score"])
            self.assertEqual(sum(row["delta"] for row in comparison["rows"]), comparison["delta"])
        amsterdam = [item for item in self.data["comparisons"].values() if item["fork"] == "amsterdam"]
        self.assertEqual(len(amsterdam), 12)
        by_eip = {item["eip"]: item for item in amsterdam}
        self.assertEqual((by_eip[7928]["human_total"], by_eip[7928]["llm_total"], by_eip[7928]["confounds"]["primary_llm_total"]), (29, 26, 40))

    def test_human_llm_alignment_matches_task05c(self) -> None:
        alignment = self.data["human_llm"]
        self.assertEqual(alignment["summary"]["comparison_count"], 12)
        self.assertEqual([row["eip"] for row in alignment["rows"][:3]], [7928, 8037, 8038])
        self.assertEqual((alignment["summary"]["mean_absolute_delta"], alignment["summary"]["mean_signed_delta"]), (5.3333, 2.8333))
        by_id = {item["id"]: item for item in alignment["criteria"]}
        self.assertEqual(by_id["security_risks"]["mean_delta"], 1.5)
        self.assertEqual(by_id["evm_gas_rule_changes"]["mean_delta"], -0.9167)
        self.assertEqual(sum(1 for row in alignment["rows"] if row["clean"]), 2)

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
