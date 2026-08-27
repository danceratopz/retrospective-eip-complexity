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
BASE = "/retrospective-complexity-eval/"


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


def validate() -> dict[str, int]:
    require(DIST.is_dir(), "site dist directory is missing; run npm run build")
    data_path = DIST / "generated/publication.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    require(data["schema_version"] == "1.1.0", "publication schema mismatch")
    require(data["release_state"] == "local_preview", "release state mismatch")
    rows = data["assessments"]
    historical = [row for row in rows if row["mode"] == "retrospective"]
    prospective = [row for row in rows if row["mode"] == "prospective"]
    scored_hegota = [row for row in prospective if row["status"] == "scored"]
    not_applicable = [row for row in prospective if row["status"] == "not_applicable"]
    require(len(rows) == 93, "all-forks table must contain 93 relationships")
    require(len(historical) == 49, "retrospective-only table must contain 49 relationships")
    require(len(prospective) == 44, "Hegotá table must contain 44 entries")
    require(len(scored_hegota) == 37 and sum(row["score"] for row in scored_hegota) == 776, "Hegotá score gate mismatch")
    require(len(not_applicable) == 7, "Hegotá N/A population mismatch")
    require(all(row["score"] is None and row["tier"] is None for row in not_applicable), "N/A rows must not have score or tier")
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
        shipping_by_fork["cancun"]["first_multi_el_devnet"] == "dencun-devnet-4",
        "Cancun ≥2-EL development start changed",
    )
    require(
        shipping_by_fork["amsterdam"]["projected"] is True
        and shipping_by_fork["amsterdam"]["mainnet_at"] == "2026-12-15",
        "Amsterdam projection changed",
    )
    human_llm = data["human_llm"]["rows"]
    require(len(human_llm) == 12, "human–LLM comparison must contain 12 Amsterdam EIPs")
    require(
        [(row["eip"], row["human_score"], row["llm_v1_score"], row["llm_v2_score"]) for row in human_llm[:3]]
        == [(7928, 29, 26, 40), (8037, 28, 21, 35), (8038, 20, 17, 17)],
        "human–LLM score ordering changed",
    )
    require(sum(row["clean"] for row in human_llm) == 2, "human–LLM clean comparison count changed")

    serialized = data_path.read_text(encoding="utf-8")
    forbidden = ["/home/", "/tmp/", "file://", "session_id", "prompt_path", "assessor_raw_output", "access_token", "api_key"]
    for term in forbidden:
        require(term not in serialized, f"forbidden public-data term: {term}")

    manifest_path = DIST / "generated/provenance.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest["schema_version"] == "1.1.0", "provenance schema mismatch")
    for item in manifest["generated_files"]:
        path = DIST / "generated" / item["path"]
        require(path.is_file(), f"manifest output is missing: {item['path']}")
        require(sha256(path) == item["sha256"], f"manifest output hash mismatch: {item['path']}")
    require(manifest["source_records"] == sorted(manifest["source_records"], key=lambda item: item["path"]), "source records are not stable-sorted")

    html_files = sorted(DIST.rglob("*.html"))
    require(len(html_files) == 153, f"expected 153 static pages, found {len(html_files)}")
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
    eip_index_html = (DIST / "eips/index.html").read_text(encoding="utf-8")
    hegota_html = (DIST / "prospective/hegota/index.html").read_text(encoding="utf-8")
    human_llm_html = (DIST / "human-vs-llm/index.html").read_text(encoding="utf-8")
    osaka_html = (DIST / "forks/osaka/index.html").read_text(encoding="utf-8")
    study_html = (DIST / "study/index.html").read_text(encoding="utf-8")
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
    require(eip_index_html.count('data-mode="') == 93, "EIP index relationship row count mismatch")
    require('data-table-search' in eip_index_html, "EIP index substring search is missing")
    require('data-table-fork' in eip_index_html, "EIP index fork filter is missing")
    require(eip_index_html.count('data-sort-key="') == 8, "EIP index columns must all be sortable")
    require("fork relationships" not in eip_index_html.lower(), "obsolete EIP index column remains")
    require("unique proposal" not in eip_index_html.lower(), "obsolete unique-proposal wording remains")
    require(hegota_html.count('data-mode="prospective"') == 44, "Hegotá HTML table row count mismatch")
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
