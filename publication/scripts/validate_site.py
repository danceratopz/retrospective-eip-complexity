#!/usr/bin/env python3
"""Validate the generated localhost static artifact and public data boundary."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "publication/site/dist"
BASE = "/retrospective-eip-complexity/"


class SiteError(RuntimeError):
    """Raised when the built static site violates a publication invariant."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SiteError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Document(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.h1_count = 0
        self.links: list[str] = []
        self.asset_urls: list[str] = []
        self.chart_urls: list[str] = []
        self.has_skip_link = False
        self.has_main = False
        self.has_nav = False
        self.has_title = False
        self.table_count = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "h1":
            self.h1_count += 1
        if tag == "main":
            self.has_main = True
        if tag == "nav":
            self.has_nav = True
        if tag == "table":
            self.table_count += 1
        if tag == "title":
            self._in_title = True
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
            if "skip-link" in (values.get("class") or ""):
                self.has_skip_link = True
        if tag in {"script", "img", "source", "iframe"} and values.get("src"):
            self.asset_urls.append(values["src"] or "")
        if tag == "link" and values.get("href"):
            self.asset_urls.append(values["href"] or "")
        if values.get("data-vega-spec"):
            self.chart_urls.append(values["data-vega-spec"] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and data.strip():
            self.has_title = True


def local_target(url: str) -> Path | None:
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or url.startswith("mailto:"):
        return None
    if not parsed.path:
        return None
    require(parsed.path.startswith(BASE), f"internal URL is not base-aware: {url}")
    relative = parsed.path.removeprefix(BASE)
    target = DIST / relative
    if parsed.path.endswith("/") or target.is_dir():
        target /= "index.html"
    return target


def occurrence_rows(data: dict) -> list[dict]:
    """Flatten EIP occurrences into one row per fork–EIP relationship with the primary LLM summary."""
    rows = []
    for eip in data["eips"]:
        for occurrence in eip["occurrences"]:
            primary = data["assessments"].get(occurrence["llm"]["assessment_id"]) if occurrence["llm"]["assessment_id"] else None
            revision = primary["provenance"]["assessed_revision"] if primary else {}
            rows.append(
                {
                    "assessed_revision": revision.get("commit"),
                    "assessed_revision_url": revision.get("immutable_url"),
                    "current_revision_url": revision.get("current_revision_url"),
                    "revision_history_url": revision.get("revision_history_url"),
                    "eip": occurrence["eip"],
                    "fork": occurrence["fork"],
                    "human_status": occurrence["human"]["status"],
                    "mode": occurrence["mode"],
                    "score": occurrence["llm"]["score"],
                    "scope_timing": occurrence["scope_timing"],
                    "snapshot_status": occurrence["snapshot_status"],
                    "status": "scored" if primary else "not_applicable",
                    "tier": occurrence["llm"]["tier"],
                }
            )
    return rows


def validate_domain_model(data: dict, rows: list[dict]) -> None:
    """Invariants of the schema 2.0.0 domain model that the pages depend on."""
    assessments = data["assessments"]
    require(len(assessments) == 137, f"expected 137 assessments, found {len(assessments)}")
    require(len(data["comparisons"]) == 32, "expected 32 same-rubric Human/LLM comparisons")
    require(len(data["criteria"]) == 29, "criterion registry must contain 29 criteria")
    require(set(data["rubrics"]) == {"1", "2"}, "both rubric revisions must be published")
    for assessment in assessments.values():
        order = data["rubrics"][str(assessment["rubric_revision"])]["criteria"]
        require([item["id"] for item in assessment["criteria"]] == order, f"{assessment['id']}: criterion order")
        if assessment["scored"]:
            require(sum(item["score"] for item in assessment["criteria"]) == assessment["score"], f"{assessment['id']}: total")
        else:
            require(assessment["score"] is None and assessment["tier"] is None, f"{assessment['id']}: unscored assessments carry no score")
    hegota_human = [row["human_status"] for row in rows if row["fork"] == "hegota"]
    require(
        {status: hegota_human.count(status) for status in set(hegota_human)}
        == {"complete": 2, "available_in_open_pr": 14, "in_progress": 8, "incomplete": 1, "not_available": 21},
        "Hegotá human-assessment status distribution changed",
    )
    for row in rows:
        if row["status"] == "not_applicable":
            require(row["score"] is None and row["tier"] is None, "N/A rows must not have score or tier")
    for comparison in data["comparisons"].values():
        human = assessments[comparison["human_assessment_id"]]
        llm = assessments[comparison["llm_assessment_id"]]
        require(human["rubric_revision"] == llm["rubric_revision"], f"{comparison['id']}: cross-rubric comparison")
        require(comparison["delta"] == llm["score"] - human["score"], f"{comparison['id']}: delta")


def validate() -> dict[str, int]:
    require(DIST.is_dir(), "site dist directory is missing; run npm run build")
    data_path = DIST / "generated/publication.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    require(data["schema_version"] == "2.0.0", "publication schema mismatch")
    require(data["release_state"] == "public", "release state mismatch")
    rows = occurrence_rows(data)
    validate_domain_model(data, rows)
    historical = [row for row in rows if row["mode"] == "retrospective"]
    prospective = [row for row in rows if row["mode"] == "prospective"]
    scored_hegota = [row for row in prospective if row["status"] == "scored"]
    not_applicable = [row for row in prospective if row["status"] == "not_applicable"]
    require(len(rows) == 95, "all-forks table must contain 95 relationships")
    require(len(historical) == 49, "retrospective-only table must contain 49 relationships")
    require(len(prospective) == 46, "Hegotá table must contain 46 entries")
    require(len(scored_hegota) == 39 and sum(row["score"] for row in scored_hegota) == 856, "Hegotá score gate mismatch")
    require(len(not_applicable) == 7, "Hegotá N/A population mismatch")
    require(all(row["score"] is None and row["tier"] is None for row in not_applicable), "N/A rows must not have score or tier")
    require(
        {row["snapshot_status"] for row in prospective} == {"PFI", "SFI", "CFI"},
        "Hegotá snapshot statuses are incomplete",
    )
    require(
        {row["eip"]: row["snapshot_status"] for row in prospective if row["snapshot_status"] != "PFI"}
        == {7805: "SFI", 8141: "CFI"},
        "Hegotá SFI/CFI snapshot membership mismatch",
    )
    pfi_scored = [row for row in scored_hegota if row["snapshot_status"] == "PFI"]
    require(
        len(pfi_scored) == 37 and sum(row["score"] for row in pfi_scored) == 776,
        "Hegotá original PFI subtotal changed",
    )
    expected_scope_totals = {
        "shanghai": {"included_at_cutoff": (4, 65), "added_after_cutoff": (1, 3)},
        "cancun": {"included_at_cutoff": (5, 126), "added_after_cutoff": (1, 9)},
        "prague": {"included_at_cutoff": (8, 216), "added_after_cutoff": (3, 38)},
        "osaka": {"included_at_cutoff": (8, 105), "added_after_cutoff": (4, 35)},
        "amsterdam": {"included_at_cutoff": (13, 243), "added_after_cutoff": (2, 44)},
    }
    for fork, expected_scopes in expected_scope_totals.items():
        for scope_timing, expected in expected_scopes.items():
            scoped = [
                row
                for row in historical
                if row["fork"] == fork and row["scope_timing"] == scope_timing
            ]
            require(
                (len(scoped), sum(row["score"] for row in scoped)) == expected,
                f"{fork} {scope_timing} count or score sum changed",
            )
    fork_summaries = {row["fork"]: row for row in data["forks"] if row["mode"] == "retrospective"}
    require(
        {
            fork: (
                row["score_sum"],
                row["at_cutoff_score_sum"],
                row["late_addition_score_sum"],
                row["final_scope_score_sum"],
            )
            for fork, row in fork_summaries.items()
        }
        == {
            fork: (
                expected["included_at_cutoff"][1],
                expected["included_at_cutoff"][1],
                expected["added_after_cutoff"][1],
                expected["included_at_cutoff"][1] + expected["added_after_cutoff"][1],
            )
            for fork, expected in expected_scope_totals.items()
        },
        "retrospective score_sum must represent the primary at-cutoff prediction",
    )
    for row in historical:
        commit = row["assessed_revision"]
        require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "invalid assessed EIP commit")
        require(
            row["assessed_revision_url"].startswith(f"https://github.com/ethereum/EIPs/blob/{commit}/EIPS/eip-"),
            "assessed-revision permalink mismatch",
        )
        require(
            row["current_revision_url"] == f"https://github.com/ethereum/EIPs/blob/master/EIPS/eip-{row['eip']}.md",
            "current-master EIP link mismatch",
        )
        require(
            row["revision_history_url"]
            == f"https://github.com/ethereum/EIPs/commits/master/EIPS/eip-{row['eip']}.md",
            "EIP file-history link mismatch",
        )

    shipping = data["fork_shipping"]
    require(len(shipping["rows"]) == 5, "fork-shipping chart must contain five forks")
    require("correlations" not in shipping, "five-fork correlations must not be published")
    shipping_by_fork = {row["fork"]: row for row in shipping["rows"]}
    require(
        {
            fork: (
                row["at_cutoff_eips"],
                row["total_score"],
                row["late_addition_eips"],
                row["late_addition_score_sum"],
                row["final_scope_score_sum"],
            )
            for fork, row in shipping_by_fork.items()
        }
        == {
            "shanghai": (4, 65, 1, 3, 68),
            "cancun": (5, 126, 1, 9, 135),
            "prague": (8, 216, 3, 38, 254),
            "osaka": (8, 105, 4, 35, 140),
            "amsterdam": (13, 243, 2, 44, 287),
        },
        "fork-shipping scores must use the at-cutoff prediction and retain later additions separately",
    )
    require(
        shipping_by_fork["cancun"]["first_multi_el_devnet"] == "dencun-devnet-4",
        "Cancun ≥2-EL development start changed",
    )
    require(
        shipping_by_fork["amsterdam"]["projected"] is True
        and shipping_by_fork["amsterdam"]["mainnet_at"] == "2026-12-15",
        "Amsterdam projection changed",
    )
    require(
        shipping_by_fork["amsterdam"]["high_tier_score_sum"] == 123
        and shipping_by_fork["amsterdam"]["hardest_eip"] == "EIP-7928"
        and shipping_by_fork["amsterdam"]["max_score"] == 40,
        "Amsterdam shipping summaries include a late-scope EIP",
    )

    fork_totals = json.loads((DIST / "generated/charts/fork-totals.json").read_text(encoding="utf-8"))
    require(len(fork_totals["data"]["values"]) == 10, "fork totals must contain two scope-timing rows per fork")
    require(
        {
            (row["fork"], row["scope"]): (row["eips"], row["score"])
            for row in fork_totals["data"]["values"]
        }
        == {
            (fork, "Included by cutoff"): expected["included_at_cutoff"]
            for fork, expected in expected_scope_totals.items()
        }
        | {
            (fork, "Added after cutoff"): expected["added_after_cutoff"]
            for fork, expected in expected_scope_totals.items()
        },
        "stacked fork-total chart does not preserve the cutoff split",
    )
    human_llm = data["human_llm"]["rows"]
    require(len(human_llm) == 12, "human–LLM comparison must contain 12 Amsterdam EIPs")
    require(
        [(row["eip"], row["human_score"], row["llm_v1_score"], row["llm_v2_score"]) for row in human_llm[:3]]
        == [(7928, 29, 26, 40), (8037, 28, 21, 35), (8038, 20, 17, 17)],
        "human–LLM score ordering changed",
    )
    require(sum(row["clean"] for row in human_llm) == 2, "human–LLM clean comparison count changed")

    forbidden = ["/home/", "/tmp/", "file://", "session_id", "prompt_path", "assessor_raw_output", "access_token", "api_key", "assessment-run-"]
    for generated in [data_path, DIST / "generated/compare-index.json", *sorted((DIST / "generated/downloads").glob("*.csv"))]:
        serialized = generated.read_text(encoding="utf-8")
        for term in forbidden:
            require(term not in serialized, f"forbidden public-data term in {generated.name}: {term}")

    manifest_path = DIST / "generated/provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest["schema_version"] == "2.0.0", "provenance schema mismatch")
    for item in manifest["generated_files"]:
        path = DIST / "generated" / item["path"]
        require(path.is_file(), f"manifest output is missing: {item['path']}")
        require(sha256(path) == item["sha256"], f"manifest output hash mismatch: {item['path']}")
    require(manifest["source_records"] == sorted(manifest["source_records"], key=lambda item: item["path"]), "source records are not stable-sorted")

    html_files = sorted(DIST.rglob("*.html"))
    require(len(html_files) == 155, f"expected 155 static pages, found {len(html_files)}")
    broken: list[str] = []
    chart_pages = 0
    for html_path in html_files:
        text = html_path.read_text(encoding="utf-8")
        document = Document()
        document.feed(text)
        relative = html_path.relative_to(DIST)
        require(
            "Retrospective LLM-Based Complexity Evaluations" in text,
            f"{relative}: publication title is missing",
        )
        require("cohort" not in text.lower(), f"{relative}: user-facing cohort jargon remains")
        require(document.h1_count == 1, f"{relative}: expected one h1")
        require(document.has_title, f"{relative}: title is missing")
        require(document.has_skip_link and document.has_main and document.has_nav, f"{relative}: required landmarks are missing")
        for url in document.asset_urls:
            require(not urlsplit(url).scheme and not urlsplit(url).netloc, f"{relative}: external asset request: {url}")
        for url in document.links + document.asset_urls + document.chart_urls:
            target = local_target(url)
            if target is not None and not target.is_file():
                broken.append(f"{relative}: {url}")
        if document.chart_urls:
            chart_pages += 1
            require(document.table_count or "generated/charts/" in text, f"{relative}: chart lacks table or data download")
    require(not broken, "broken internal links:\n" + "\n".join(broken[:20]))

    association_html = (DIST / "results/predicted-vs-observed/index.html").read_text(encoding="utf-8")
    home_html = (DIST / "index.html").read_text(encoding="utf-8")
    eip_index_html = (DIST / "eips/index.html").read_text(encoding="utf-8")
    hegota_html = (DIST / "prospective/hegota/index.html").read_text(encoding="utf-8")
    human_llm_html = (DIST / "human-vs-llm/index.html").read_text(encoding="utf-8")
    osaka_html = (DIST / "forks/osaka/index.html").read_text(encoding="utf-8")
    study_html = home_html
    legacy_study_html = (DIST / "study/index.html").read_text(encoding="utf-8")
    require(
        "Can Execution Layer Complexity Assessments Help Predict Time to Mainnet?" in study_html,
        "study question or Execution Layer scope is missing",
    )
    require(
        "retrospective complexity assessments from early Execution Layer EIP specifications" in study_html,
        "LLM assessment disclosure or Execution Layer scope is missing",
    )
    require("Only the Execution Layer surface is scored." in study_html, "cross-layer scoring boundary is missing")
    require(
        "independently of the STEEL team’s ongoing manual assessment work" in study_html,
        "Hegotá manual-assessment independence disclosure is missing from the study",
    )
    require("https://steel.ethereum.foundation/" in study_html, "STEEL team link is missing")
    require(
        "https://github.com/ethspecs/pm/blob/3d8c0128c5543dd3146341ef395aa344e4abea30/Templates/EIP-Complexity-Assessment.md"
        in study_html,
        "complexity-assessment template link is missing",
    )
    require("id=\"background\"" in study_html, "study background is missing")
    require("id=\"limitations\"" in study_html, "study limitations are missing")
    require("Method before results" not in study_html, "obsolete study eyebrow remains")
    require("Evaluation-first research publication" not in home_html, "obsolete landing-page eyebrow remains")
    require("How much complexity did an EIP imply before implementation?" not in home_html, "obsolete landing page remains")
    require(
        'href="/retrospective-eip-complexity/">Study</a>' in home_html,
        "Study navigation must point to the homepage",
    )
    require(
        'href="https://github.com/danceratopz/retrospective-eip-complexity"' in home_html
        and 'aria-label="View the source repository on GitHub (opens in a new tab)"' in home_html,
        "accessible source-repository link is missing",
    )
    require(
        'http-equiv="refresh" content="0; url=/retrospective-eip-complexity/"' in legacy_study_html
        and '<meta name="robots" content="noindex">' in legacy_study_html,
        "legacy Study route must redirect to the homepage",
    )
    for label in ["Score at cutoff", "Added-later score", "Final-scope score"]:
        require(label in association_html, f"association page omits {label.lower()}")
    require(
        association_html.count('data-sort-key="') == 14,
        "results fork-total and shipping columns must all be sortable",
    )
    for removed_route in [
        "data",
        "limitations",
        "reproduce",
        "results/human-automated-alignment",
        "results/observed-effort",
        "results/predicted-complexity",
        "study/question-and-population",
        "study/workflow",
    ]:
        require(not (DIST / removed_route / "index.html").exists(), f"obsolete route remains: {removed_route}")
    require(eip_index_html.count('data-mode="') == 95, "EIP index relationship row count mismatch")
    require('data-table-search' in eip_index_html, "EIP index substring search is missing")
    require('data-table-fork' in eip_index_html, "EIP index fork filter is missing")
    require(eip_index_html.count('data-sort-key="') == 8, "EIP index columns must all be sortable")
    require("fork relationships" not in eip_index_html.lower(), "obsolete EIP index column remains")
    require("unique proposal" not in eip_index_html.lower(), "obsolete unique-proposal wording remains")
    require(hegota_html.count('data-mode="prospective"') == 46, "Hegotá HTML table row count mismatch")
    require('data-sortable-table' in hegota_html, "Hegotá assessment table is not sortable")
    require(hegota_html.count('data-sort-key="') == 9, "Hegotá assessment columns must all be sortable")
    require("Snapshot status" in hegota_html, "Hegotá snapshot-status column is missing")
    require(
        "Hegotá SFI'd/CFI'd EIPs at the time of the 2026-08-26 snapshot" in hegota_html,
        "Hegotá SFI/CFI snapshot disclosure is missing",
    )
    require(
        "independently of the STEEL team’s ongoing manual assessment work" in hegota_html,
        "Hegotá manual-assessment independence disclosure is missing",
    )
    require("<strong>Independent LLM Evaluation.</strong>" in hegota_html, "Hegotá LLM disclosure is not emphasized")
    require(
        "Execution Layer and execution-client networking surfaces only" in hegota_html,
        "Hegotá Execution Layer scope is missing",
    )
    require("data-retrospective-only" in eip_index_html, "retrospective-only filter is missing")
    hegota_chart = json.loads((DIST / "generated/charts/hegota-scores.json").read_text(encoding="utf-8"))
    require(
        len(hegota_chart["data"]["values"]) == 39
        and all(row.get("title") for row in hegota_chart["data"]["values"]),
        "Hegotá chart must carry every scored EIP title",
    )
    require(
        {row["snapshot_status"] for row in hegota_chart["data"]["values"]} == {"PFI", "SFI", "CFI"},
        "Hegotá chart snapshot statuses are incomplete",
    )
    require(
        any(item.get("field") == "title" and item.get("title") == "EIP name" for item in hegota_chart["encoding"]["tooltip"]),
        "Hegotá chart tooltip is missing EIP names",
    )
    require(
        association_html.index("generated/charts/fork-totals.json")
        < association_html.index("generated/charts/fork-shipping.json"),
        "fork totals must be the first Results plot",
    )
    for chart in ["fork-shipping", "fork-shipping-high-tier", "fork-shipping-hardest-eip"]:
        require(f"generated/charts/{chart}.json" in association_html, f"{chart} chart is missing")
        chart_text = (DIST / f"generated/charts/{chart}.json").read_text(encoding="utf-8")
        require("Spearman" not in chart_text and "Pearson" not in chart_text, f"{chart} publishes unstable correlations")
        chart_spec = json.loads(chart_text)
        require(chart_spec["width"] == chart_spec["height"] == 500, f"{chart} plotting area must be square")
    require(
        "Fork Shipping Time Versus Predicted Complexity" in association_html,
        "fork-shipping section title must appear outside the charts",
    )
    require("Fork-level correlation summary" not in association_html, "five-fork correlation cards remain")
    require(association_html.count('data-shipping-fork="') == 5, "fork-shipping table row count mismatch")
    observed_charts = {
        "predicted-observed-specification-rework": "Specification rework",
        "predicted-observed-eip-interactions": "New EIP interactions",
    }
    for chart, metric in observed_charts.items():
        require(f"generated/charts/{chart}.json" in association_html, f"{metric} chart is missing")
        observed_spec = json.loads((DIST / f"generated/charts/{chart}.json").read_text(encoding="utf-8"))
        observed_metrics = {row["metric"] for row in observed_spec["data"]["values"]}
        require(observed_metrics == {metric}, f"{metric} chart contains another proxy")
        require(len(observed_spec["data"]["values"]) == 34, f"{metric} must contain the 34 shipped-fork relationships")
        require(
            {row["fork"] for row in observed_spec["data"]["values"]}
            == {"Shanghai / Shapella", "Cancun / Dencun", "Prague / Pectra", "Osaka / Fusaka"},
            f"{metric} chart must exclude incomplete Amsterdam observations",
        )
        require("shape" not in observed_spec["encoding"] and "strokeDash" not in observed_spec["encoding"], f"{metric} retains censor encoding")
        require(observed_spec["width"] == observed_spec["height"] == 500, f"{metric} plotting area must be square")
    require("generated/charts/predicted-observed.json" not in association_html, "combined horizontal proxy chart remains")
    require("Amsterdam is omitted from these plots" in association_html, "Amsterdam exclusion is unexplained")
    require("right-censored" not in association_html.lower(), "censoring jargon remains on results page")
    require(">34</td>" in association_html, "shipped-fork correlation sample size is incorrect")
    require("counts substantive revisions" in association_html, "specification-rework proxy is unexplained")
    require("counts distinct <code>requires</code> or <code>interacts_with</code>" in association_html, "EIP-interaction proxy is unexplained")
    require("Emergent coupling" not in association_html, "jargon-heavy proxy label remains")
    require("generated/charts/human-alignment.json" in human_llm_html, "human–LLM chart is missing")
    require(human_llm_html.count('data-human-llm-eip="') == 12, "human–LLM table row count mismatch")
    require(human_llm_html.count('data-sort-key="') == 6, "human–LLM columns must all be sortable")
    require(">Block-Level Access Lists</td>" in human_llm_html, "human–LLM proposal titles are missing")
    require("The LLM applied a “risk-review tax.”" in human_llm_html, "human–LLM systematic difference is missing")
    require("currently the only fork with a completed human complexity evaluation" in human_llm_html, "Amsterdam comparison rationale is missing")
    require("manual evaluation for Hegotá is still underway" in human_llm_html, "Hegotá manual-evaluation status is missing")
    require("structured sanity check" in human_llm_html, "human–LLM sanity-check framing is missing")
    require("The two LLM evaluations differ only in the template." in human_llm_html, "controlled template comparison is not prominent")
    require(
        "https://github.com/ethspecs/pm/blob/d936bcb34963cb5eec015dada2e4188e49fc14d5/Templates/EIP-Complexity-Assessment.md"
        in human_llm_html,
        "complexity-assessment template v1 permalink is missing",
    )
    require(
        "https://github.com/ethspecs/pm/blob/3d8c0128c5543dd3146341ef395aa344e4abea30/Templates/EIP-Complexity-Assessment.md"
        in human_llm_html,
        "complexity-assessment template v2 permalink is missing",
    )
    require("No proposal revision or implementation evidence changed between them." in human_llm_html, "controlled LLM inputs are unclear")
    require("Only two EIPs meet" not in human_llm_html, "secondary clean-subset warning remains prominent")
    require(osaka_html.count(">Current master</a>") == 12, "Osaka current-revision links are incomplete")
    require(osaka_html.count(">File history</a>") == 12, "Osaka file-history links are incomplete")
    require(
        osaka_html.index("Complexity Assessments") < osaka_html.index("How the Historical Refs Were Selected"),
        "fork assessment table must precede the supporting timeline",
    )
    require(
        "generated/charts/fork-milestones-osaka.json" in osaka_html
        and "generated/charts/timeline-osaka.json" in osaka_html,
        "Osaka fork and EIP timelines must render separately",
    )
    require(osaka_html.count("data-fit-chart") == 2, "Osaka timelines must opt into responsive fitting")
    require(osaka_html.count("data-fork-link") == 6, "Osaka quick navigation must include every fork")
    require('aria-current="page"' in osaka_html, "Osaka quick navigation must identify the current fork")
    require(osaka_html.count('data-sort-key="') == 7, "Osaka assessment columns must all be sortable")
    require("GPT-5.6 Sol LLM at xhigh reasoning effort" in osaka_html, "fork assessment method is missing")
    require(
        "https://github.com/ethspecs/pm/blob/3d8c0128c5543dd3146341ef395aa344e4abea30/Templates/EIP-Complexity-Assessment.md"
        in osaka_html,
        "STEEL template permalink is missing",
    )
    require("Current master” and “File history”" not in osaka_html, "obsolete GitHub-link prose remains")
    require("timeline-guide" not in osaka_html, "timeline key must use a simple list")
    require("The main purpose of this panel" in osaka_html, "EIP-history purpose is unexplained")

    fork_links = {}
    for fork in ["shanghai", "cancun", "prague", "osaka", "amsterdam"]:
        document = Document()
        document.feed((DIST / f"forks/{fork}/index.html").read_text(encoding="utf-8"))
        fork_links[fork] = set(document.links)
    for row in historical:
        detail = Document()
        detail.feed(
            (DIST / f"forks/{row['fork']}/eips/{row['eip']}/index.html").read_text(encoding="utf-8")
        )
        for url in [row["assessed_revision_url"], row["current_revision_url"], row["revision_history_url"]]:
            require(url in fork_links[row["fork"]], f"fork page omits EIP-{row['eip']} revision link")
            require(url in detail.links, f"assessment page omits EIP-{row['eip']} revision link")

    for fork in ["shanghai", "cancun", "prague", "osaka", "amsterdam"]:
        milestone_path = DIST / f"generated/charts/fork-milestones-{fork}.json"
        milestone = json.loads(milestone_path.read_text(encoding="utf-8"))
        require(milestone["width"] <= 1080, f"{fork} milestone timeline is too wide")
        require("vconcat" not in milestone, f"{fork} milestone timeline was not separated")

        timeline_path = DIST / f"generated/charts/timeline-{fork}.json"
        timeline_text = timeline_path.read_text(encoding="utf-8")
        require("cohort" not in timeline_text.lower(), f"{fork} timeline contains cohort jargon")
        timeline = json.loads(timeline_text)
        require(timeline["spec"]["width"] <= 820, f"{fork} EIP timelines are too wide")
        require("vconcat" not in timeline, f"{fork} EIP timeline was not separated")
        x_encodings = [
            item["encoding"]["x"]
            for item in timeline["spec"]["layer"]
            if "x" in item.get("encoding", {})
        ]
        require(x_encodings, f"{fork} EIP timeline has no time encoding")
        require(
            len({tuple(item["scale"]["domain"]) for item in x_encodings}) == 1,
            f"{fork} EIP timeline rows do not share one date domain",
        )
        require(
            all(
                item["axis"].get("labels")
                and item["axis"].get("ticks")
                and item["axis"].get("orient") == "top"
                for item in x_encodings
            ),
            f"{fork} EIP timeline shared time axis is not visible",
        )

    js_files = sorted((DIST / "_astro").glob("*.js"))
    require(js_files, "bundled JavaScript is missing")
    largest_compressed_js = max(len(gzip.compress(path.read_bytes())) for path in js_files)
    require(largest_compressed_js <= 500 * 1024, f"shared JavaScript exceeds 500 KiB compressed: {largest_compressed_js}")
    chart_files = sorted((DIST / "generated/charts").glob("*.json"))
    require(all(path.stat().st_size < 2 * 1024 * 1024 for path in chart_files), "chart payload exceeds 2 MiB")

    return {
        "chart_pages": chart_pages,
        "html_pages": len(html_files),
        "largest_compressed_js": largest_compressed_js,
        "records": len(rows),
    }


if __name__ == "__main__":
    try:
        print(json.dumps(validate(), sort_keys=True))
    except SiteError as error:
        raise SystemExit(f"site validation error: {error}") from error
