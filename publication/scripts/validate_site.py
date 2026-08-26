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

    shipping = data["fork_shipping"]
    require(len(shipping["rows"]) == 5, "fork-shipping chart must contain five forks")
    require(
        [item["spearman_rho"] for item in shipping["correlations"]] == [0.4, 0.5, 0.9],
        "fork-shipping rank correlations changed",
    )
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
    require(len(html_files) == 165, f"expected 165 static pages, found {len(html_files)}")
    broken: list[str] = []
    chart_pages = 0
    for html_path in html_files:
        text = html_path.read_text(encoding="utf-8")
        document = Document()
        document.feed(text)
        relative = html_path.relative_to(DIST)
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

    predicted_html = (DIST / "results/predicted-complexity/index.html").read_text(encoding="utf-8")
    association_html = (DIST / "results/predicted-vs-observed/index.html").read_text(encoding="utf-8")
    hegota_html = (DIST / "prospective/hegota/index.html").read_text(encoding="utf-8")
    require(predicted_html.count('data-mode="') == 93, "all-forks HTML table row count mismatch")
    require(hegota_html.count('data-mode="prospective"') == 44, "Hegotá HTML table row count mismatch")
    require("data-retrospective-only" in predicted_html, "retrospective-only filter is missing")
    require("generated/charts/fork-shipping.json" in association_html, "primary fork-shipping chart is missing")
    require(association_html.count('data-shipping-fork="') == 5, "fork-shipping table row count mismatch")

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
