#!/usr/bin/env -S uv run --script
#
# /// script
# dependencies = [
#   "pyyaml",
#   "pandas",
#   "scipy",
#   "altair",
#   "vl-convert-python",
# ]
# ///
"""Task 07: predicted-vs-observed dot plots (interactive HTML) and rank correlations.

THIS SCRIPT READS TASK 05 PREDICTED SCORES. It is the prediction-outcome join
and must only run once all 49 original assessments exist. It refuses to run on
a partial assessment set unless --allow-partial is given.

Outputs (all under outputs/join/):
  predicted-vs-observed.csv    joined analysis table
  rank-correlations.csv        Spearman/Kendall per metric
  dashboard.html               all six panels on one page
  metric-<name>.html           one interactive chart per metric
  dashboard.png                raster render for quick visual checks
  table.html                   full joined table (relief/table view)
  index.html                   entry page linking everything

Design: light-committed pages; categorical palette validated with the dataviz
six-checks validator in all-pairs mode (worst CVD pair 6.9 -> forks also carry
distinct marker shapes as secondary encoding; sub-3:1 hues relieved by the
table view). Amsterdam renders as open markers: right-censored, in-sample.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import yaml
from scipy import stats

TASK_DIR = Path(__file__).resolve().parent.parent
TASKS = TASK_DIR.parent
T05 = TASKS / "05-retrospective-complexity-assignment" / "outputs" / "fork-eips"
T03 = TASKS / "03-fork-development-timelines" / "inputs" / "forks"
OUT = TASK_DIR / "outputs"
JOIN = OUT / "join"

# Planning assumption supplied by the reviewer (2026-08-26), NOT an observed
# milestone: Amsterdam mainnet projected mid-December 2026.
PROJECTED_MAINNET = {"amsterdam": "2026-12-15"}

# Stricter span-start variant: first devnet with >=2 independent EL
# implementations. Only Cancun differs from the first-EL-devnet definition:
# devnets 1-3 ran a single patched go-ethereum fork (inphi/geth), and
# devnet-4 launched with geth + nethermind (ethpandaops/dencun-devnets
# inventory at commit 94ae639, 2023-01; erigon/besu joined during its life).
# The other forks' devnet series were multi-EL from their first devnet
# (Shanghai withdrawals devnets ran geth+nethermind+besu pairs per ACD 151;
# Prague/Osaka/Amsterdam are ethpandaops-era client-matrix launches).
MULTI_EL_FIRST_DEVNET = {"cancun": "dencun-devnet-4"}

EXPECTED_ROWS = 49
FORKS = ["shanghai", "cancun", "prague", "osaka", "amsterdam"]
FORK_LABELS = {
    "shanghai": "Shanghai/Shapella (2023)",
    "cancun": "Cancun/Dencun (2024)",
    "prague": "Prague/Pectra (2025)",
    "osaka": "Osaka/Fusaka (2025)",
    "amsterdam": "Amsterdam/Glamsterdam (censored)",
}
# Validated 5-hue set (dataviz validator, --pairs all, light surface #fcfcfb):
# worst CVD pair 6.9 (aqua-red) -> shapes below are the required secondary
# encoding; aqua and yellow are sub-3:1 on the surface -> table.html is the
# relief view. Amsterdam takes violet and renders unfilled (censored).
FORK_COLORS = {
    "shanghai": "#2a78d6",   # blue
    "cancun": "#e34948",     # red
    "prague": "#1baf7a",     # aqua
    "osaka": "#eda100",      # yellow
    "amsterdam": "#4a3aa7",  # violet
}
FORK_SHAPES = {
    "shanghai": "circle",
    "cancun": "square",
    "prague": "triangle-up",
    "osaka": "diamond",
    "amsterdam": "triangle-down",
}

# Cohort split for the fork-totals bar (validated adjacent pair, slots 1-2).
COHORTS = ["forecastable_at_cutoff", "late_scope"]
COHORT_COLORS = {"forecastable_at_cutoff": "#2a78d6", "late_scope": "#eb6834"}
COHORT_LABELS = {
    "forecastable_at_cutoff": "Forecastable at initial scope cutoff",
    "late_scope": "Late-scope addition",
}

INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"

PANELS = [
    ("days_cutoff_to_mainnet", "Delivery lead time",
     "Calendar days from the frozen assessment-information cutoff to mainnet "
     "activation — delivery exposure, not effort (Amsterdam absent: not yet live)."),
    ("subst_revisions_after_cutoff", "Specification rework",
     "Substantive EIP-text revisions between the assessment cutoff and mainnet "
     "(Amsterdam: 2026-08-25 censor)."),
    ("devnet_count", "Integration exposure",
     "Fork-series devnets whose published configuration explicitly activated "
     "the EIP."),
    ("deps_final", "Coordination surface",
     "Distinct requires/interacts-with EIPs evidenced in the EIP's history by "
     "the end of the observation window."),
    ("deps_after_cutoff", "Emergent coupling",
     "Dependencies whose first evidence postdates the assessment cutoff — "
     "coupling discovered during development."),
    ("observed_effort_composite_v0", "Observed-effort composite v0",
     "Equal-weight mean of within-fork percentile ranks of revisions, devnet "
     "count, and dependencies (0-1; lead time deliberately excluded)."),
]


def load_predictions() -> pd.DataFrame:
    rows = []
    for fork in FORKS:
        for path in sorted((T05 / fork).glob("eip-*.yaml")):
            with path.open() as fh:
                doc = yaml.safe_load(fh)
            rows.append({
                "fork": fork,
                "eip": doc["eip"]["number"],
                "eip_title": doc["eip"]["title"],
                "predicted_score": doc["totals"]["primary_score"],
                "predicted_tier": doc["totals"]["complexity_tier"],
            })
    return pd.DataFrame(rows)


def correlations(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, name, _ in PANELS:
        sub = df[["predicted_score", col, "fork"]].dropna()
        rho, rho_p = stats.spearmanr(sub["predicted_score"], sub[col])
        tau, tau_p = stats.kendalltau(sub["predicted_score"], sub[col])
        per_fork = [
            stats.spearmanr(g["predicted_score"], g[col]).statistic
            for _, g in sub.groupby("fork")
            if len(g) >= 4 and g[col].nunique() > 1
        ]
        rows.append({
            "metric": col, "label": name, "n": len(sub),
            "spearman_rho": round(rho, 3), "spearman_p": round(rho_p, 4),
            "kendall_tau": round(tau, 3), "kendall_p": round(tau_p, 4),
            "mean_within_fork_spearman":
                round(sum(per_fork) / len(per_fork), 3) if per_fork else None,
            "forks_in_within_mean": len(per_fork),
        })
    return pd.DataFrame(rows)


def base_config(chart: alt.Chart | alt.VConcatChart) -> alt.Chart:
    return (
        chart
        .configure(background=SURFACE, font=FONT)
        .configure_axis(labelColor=MUTED, titleColor=INK2, gridColor=GRID,
                        domainColor=BASELINE, tickColor=BASELINE)
        .configure_legend(labelColor=INK2, titleColor=INK2, labelLimit=300)
        .configure_title(color=INK, subtitleColor=INK2, anchor="start")
        .configure_view(stroke=None)
    )


def make_panel(df: pd.DataFrame, col: str, name: str, explainer: str,
               stats_row: dict, interactive_legend: bool) -> alt.LayerChart:
    data = df.dropna(subset=[col]).copy()
    # Integer-quantized axes produce exactly coincident points that hide one
    # another (e.g. two EIPs at the same score and revision count). Nudge only
    # exact duplicates apart on x, symmetrically around the true score; the
    # tooltip keeps the unmodified value.
    key = ["predicted_score", col]
    rank_in_group = data.groupby(key).cumcount()
    group_size = data.groupby(key)[col].transform("size")
    data["x_plot"] = (data["predicted_score"]
                      + (rank_in_group - (group_size - 1) / 2) * 0.6)
    n_dodged = int((group_size > 1).sum())
    color = alt.Color(
        "fork:N", title="Fork",
        scale=alt.Scale(domain=FORKS, range=[FORK_COLORS[f] for f in FORKS]),
        legend=alt.Legend(labelExpr=str(
            {f: FORK_LABELS[f] for f in FORKS}) + "[datum.value]"),
    )
    shape = alt.Shape(
        "fork:N", title="Fork",
        scale=alt.Scale(domain=FORKS, range=[FORK_SHAPES[f] for f in FORKS]),
    )
    x = alt.X("x_plot:Q", title="Predicted complexity score",
              scale=alt.Scale(domain=[0, 50], nice=False))
    ymax = float(data[col].max())
    y = alt.Y(f"{col}:Q", title=name,
              scale=alt.Scale(domain=[0, ymax * 1.08 if ymax > 0 else 1],
                              nice=False, zero=True))
    tooltip = [
        alt.Tooltip("eip:N", title="EIP"),
        alt.Tooltip("eip_title:N", title="Title"),
        alt.Tooltip("fork:N", title="Fork"),
        alt.Tooltip("predicted_score:Q", title="Predicted score"),
        alt.Tooltip("predicted_tier:N", title="Predicted tier"),
        alt.Tooltip(f"{col}:Q", title=name, format=".3~f"),
        alt.Tooltip("cohort:N", title="Cohort"),
    ]

    sel = alt.selection_point(fields=["fork"], bind="legend", name=f"sel_{col}")
    opacity = (alt.condition(sel, alt.value(0.9), alt.value(0.12))
               if interactive_legend else alt.value(0.9))

    solid = alt.Chart(data).transform_filter(
        alt.datum.censored == False  # noqa: E712
    ).mark_point(filled=True, size=90, stroke=SURFACE, strokeWidth=1).encode(
        x=x, y=y, color=color, shape=shape, tooltip=tooltip, opacity=opacity)
    hollow = alt.Chart(data).transform_filter(
        alt.datum.censored == True  # noqa: E712
    ).mark_point(filled=False, size=90, strokeWidth=2).encode(
        x=x, y=y, color=color, shape=shape, tooltip=tooltip, opacity=opacity)

    tiers = alt.Chart(pd.DataFrame({"x": [12, 23]})).mark_rule(
        color=BASELINE, strokeDash=[4, 4]).encode(x="x:Q")
    tier_labels = alt.Chart(pd.DataFrame(
        {"x": [6, 17.5, 36], "label": ["Low", "Medium", "High"]}
    )).mark_text(color=MUTED, dy=-4, fontSize=10, font=FONT).encode(
        x="x:Q", y=alt.value(8), text="label:N")

    within = stats_row["mean_within_fork_spearman"]
    stats_line = (
        f"Spearman ρ = {stats_row['spearman_rho']:.2f} "
        f"(p = {stats_row['spearman_p']:.3g}) · "
        f"Kendall τ = {stats_row['kendall_tau']:.2f} · "
        f"mean within-fork ρ = "
        f"{within:.2f} ({stats_row['forks_in_within_mean']} forks)"
        if within is not None else
        f"Spearman ρ = {stats_row['spearman_rho']:.2f} "
        f"(p = {stats_row['spearman_p']:.3g}) · "
        f"Kendall τ = {stats_row['kendall_tau']:.2f}"
    )
    if n_dodged:
        stats_line += (f" · {n_dodged} exactly coincident points nudged "
                       "±0.3 on x")
    layered = (tiers + tier_labels + solid + hollow).properties(
        width=420, height=300,
        title=alt.TitleParams(
            text=f"{name} · n = {stats_row['n']}",
            subtitle=[explainer, stats_line],
            fontSize=14, subtitleFontSize=11),
    )
    if interactive_legend:
        layered = layered.add_params(sel)
    return layered


def make_fork_totals(df: pd.DataFrame) -> alt.LayerChart:
    agg = (df.groupby(["fork", "cohort"], as_index=False)
             .agg(total=("predicted_score", "sum"), eips=("eip", "count")))
    totals = (df.groupby("fork", as_index=False)
                .agg(total=("predicted_score", "sum"), eips=("eip", "count")))
    fork_axis = alt.X(
        "fork:N", title=None, sort=FORKS,
        axis=alt.Axis(labelAngle=0, labelExpr=str(
            {"shanghai": "Shanghai", "cancun": "Cancun", "prague": "Prague",
             "osaka": "Osaka", "amsterdam": "Amsterdam*"}) + "[datum.value]"))
    bars = alt.Chart(agg).mark_bar(stroke=SURFACE, strokeWidth=2, size=52).encode(
        x=fork_axis,
        y=alt.Y("total:Q", title="Sum of predicted complexity scores"),
        color=alt.Color(
            "cohort:N", title="Cohort (Task 04b, provisional)",
            scale=alt.Scale(domain=COHORTS,
                            range=[COHORT_COLORS[c] for c in COHORTS]),
            legend=alt.Legend(labelExpr=str(COHORT_LABELS) + "[datum.value]")),
        order=alt.Order("cohort:N", sort="ascending"),
        tooltip=[
            alt.Tooltip("fork:N", title="Fork"),
            alt.Tooltip("cohort:N", title="Cohort"),
            alt.Tooltip("total:Q", title="Score subtotal"),
            alt.Tooltip("eips:Q", title="EIPs in cohort"),
        ])
    labels = alt.Chart(totals).mark_text(
        dy=-8, color=INK2, fontSize=12, font=FONT, fontWeight="bold").encode(
        x=fork_axis, y="total:Q", text="total:Q")
    counts = alt.Chart(totals).mark_text(
        dy=-24, color=MUTED, fontSize=10, font=FONT).encode(
        x=fork_axis, y="total:Q",
        text=alt.Text("eips:Q", format=".0f"))
    counts = counts.transform_calculate(label="datum.eips + ' EIPs'").encode(
        text="label:N")
    return (bars + labels + counts).properties(
        width=420, height=300,
        title=alt.TitleParams(
            text="Total predicted complexity per fork",
            subtitle=[
                "Sum of per-EIP predicted scores, split by Task 04b cohort "
                "(provisional): forecastable at the initial scope cutoff vs "
                "late-scope additions.",
                "*Amsterdam is still in development (scope may grow) and "
                "potentially in-sample. Sums also reflect EIP count and "
                "specification-splitting choices, not effort alone."],
            fontSize=14, subtitleFontSize=11))


def parse_dt(value):
    s = str(value)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    from datetime import datetime, timezone
    dt = datetime.fromisoformat(s)
    return (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None
            else dt.astimezone(timezone.utc))


def make_fork_shipping(df: pd.DataFrame) -> alt.HConcatChart:
    display = {"shanghai": "Shanghai", "cancun": "Cancun", "prague": "Prague",
               "osaka": "Osaka", "amsterdam": "Amsterdam (projected)"}
    rows = []
    for fork in FORKS:
        with (T03 / f"{fork}.yaml").open() as fh:
            t3 = yaml.safe_load(fh)
        mainnet = next((m["occurred_at"] for m in t3["milestones"]
                        if m.get("kind") == "mainnet"), None)
        projected = mainnet is None
        end = parse_dt(mainnet if mainnet else PROJECTED_MAINNET[fork])
        g = df[df.fork == fork]
        el_eips = set(g.eip)
        first_el = min(
            (parse_dt(d["occurred_at"]), d["id"])
            for d in t3["devnets"]
            if el_eips & set(d.get("participation") or []))
        maxrow = g.loc[g.predicted_score.idxmax()]
        high = g[g.predicted_tier == "high"]
        multi_id = MULTI_EL_FIRST_DEVNET.get(fork)
        if multi_id:
            multi_at = next(parse_dt(d["occurred_at"]) for d in t3["devnets"]
                            if d["id"] == multi_id)
            span_multi = (end - multi_at).days
        else:
            multi_id, span_multi = first_el[1], (end - first_el[0]).days
        rows.append({
            "fork": fork, "label": display[fork],
            "total": int(g.predicted_score.sum()),
            "high_sum": int(high.predicted_score.sum()),
            "n_high": len(high),
            "high_eips": ", ".join(str(e) for e in sorted(high.eip)),
            "max_score": int(maxrow.predicted_score),
            "max_eip": f"EIP-{maxrow.eip} {maxrow.eip_title}",
            "span_days": span_multi,
            "start_devnet": multi_id,
            "span_first_el_days": (end - first_el[0]).days,
            "first_el_devnet": first_el[1],
            "first_el_devnet_at": first_el[0].date().isoformat(),
            "mainnet": end.date().isoformat()
                       + (" (projected)" if projected else ""),
            "projected": projected,
        })
    ships = pd.DataFrame(rows)

    def panel(xcol, xtitle, note):
        rho = stats.spearmanr(ships[xcol], ships["span_days"]).statistic
        r = stats.pearsonr(ships[xcol], ships["span_days"]).statistic
        x = alt.X(f"{xcol}:Q", title=xtitle,
                  scale=alt.Scale(domain=[0, float(ships[xcol].max()) * 1.15],
                                  nice=False))
        y = alt.Y("span_days:Q", title="Days: first ≥2-EL devnet → mainnet",
                  scale=alt.Scale(domain=[0, float(ships["span_days"].max())
                                          * 1.1], nice=False))
        color = alt.Color("fork:N", legend=None, scale=alt.Scale(
            domain=FORKS, range=[FORK_COLORS[f] for f in FORKS]))
        tooltip = [
            alt.Tooltip("label:N", title="Fork"),
            alt.Tooltip("total:Q", title="Summed score"),
            alt.Tooltip("high_sum:Q", title="High-tier sum"),
            alt.Tooltip("n_high:Q", title="High-tier EIPs"),
            alt.Tooltip("high_eips:N", title="High-tier EIP numbers"),
            alt.Tooltip("max_score:Q", title="Hardest EIP score"),
            alt.Tooltip("max_eip:N", title="Hardest EIP"),
            alt.Tooltip("span_days:Q", title="Days ≥2-EL devnet→mainnet"),
            alt.Tooltip("start_devnet:N", title="First ≥2-EL devnet"),
            alt.Tooltip("span_first_el_days:Q",
                        title="Days from first EL devnet (any count)"),
            alt.Tooltip("first_el_devnet:N",
                        title="First EL devnet (any count)"),
            alt.Tooltip("mainnet:N", title="Mainnet"),
        ]
        solid = alt.Chart(ships).transform_filter(
            alt.datum.projected == False  # noqa: E712
        ).mark_point(filled=True, size=140, stroke=SURFACE,
                     strokeWidth=1).encode(
            x=x, y=y, color=color, tooltip=tooltip)
        hollow = alt.Chart(ships).transform_filter(
            alt.datum.projected == True  # noqa: E712
        ).mark_point(filled=False, size=140, strokeWidth=2).encode(
            x=x, y=y, color=color, tooltip=tooltip)
        labels = alt.Chart(ships).mark_text(
            align="left", dx=10, font=FONT, fontSize=11,
            color=INK2).encode(x=x, y=y, text="label:N")

        return (solid + hollow + labels).properties(
            width=330, height=300,
            title=alt.TitleParams(
                text=xtitle + " · Spearman ρ = %.2f · Pearson r = %.2f"
                     % (rho, r),
                subtitle=[note,
                          "n = 5 forks — descriptive only, no significance "
                          "is possible at this sample size."],
                fontSize=13, subtitleFontSize=11))

    left = panel(
        "total", "Summed predicted complexity (final scope)",
        "Sum of all execution-affecting EIP scores in the fork. Parallelized "
        "across teams, so a weak delivery predictor.")
    middle = panel(
        "high_sum", "Sum of High-tier EIP scores only",
        "Cumulative score of EIPs predicted High (≥ 23): the heavy-hitter "
        "load, between the total-load and single-critical-path hypotheses.")
    right = panel(
        "max_score", "Hardest single EIP (max predicted score)",
        "The fork's critical path: the headliner that anchors the devnet "
        "series. Caveat: Cancun's devnets 4–7 were still 4844-only feature "
        "devnets, so its span partly measures the headliner's own phase.")
    return alt.hconcat(
        left, middle, right,
        title=alt.TitleParams(
            text="Fork ship time vs predicted complexity",
            subtitle=["Development-start definition (enshrined 2026-08-26, "
                      "aligned with Task 02's 'underway in earnest' "
                      "heuristic): the fork's first devnet running ≥2 "
                      "independent EL implementations. Only Cancun differs "
                      "from a first-EL-devnet reading — its devnets 1–3 ran "
                      "a single patched geth fork, so its clock starts at "
                      "dencun-devnet-4.",
                      "Amsterdam open markers use the projected mid-December "
                      "2026 mainnet (planning assumption, 2026-08-26).",
                      "Cancun alone separates the hypotheses: without it the "
                      "plain sum is near-perfect (ρ = 1.00, r = 1.00) and max "
                      "drops to ρ = 0.80 — at n = 5, one fork decides which "
                      "reading wins."],
            fontSize=15, subtitleFontSize=11, anchor="start"))


def write_index(corr: pd.DataFrame) -> None:
    rows = "\n".join(
        f"<tr><td><a href='metric-{r.metric}.html'>{r.label}</a></td>"
        f"<td>{r.n}</td><td>{r.spearman_rho:.2f}</td><td>{r.spearman_p:.3g}</td>"
        f"<td>{r.kendall_tau:.2f}</td>"
        f"<td>{'' if r.mean_within_fork_spearman is None else f'{r.mean_within_fork_spearman:.2f}'}</td></tr>"
        for r in corr.itertuples()
    )
    legend = " ".join(
        f"<span style='color:{FORK_COLORS[f]};font-weight:600'>&#9679; "
        f"{FORK_LABELS[f]}</span>"
        for f in FORKS
    )
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Predicted vs observed effort — retrospective complexity eval</title>
<style>
 body {{ background:{PAGE}; color:{INK}; font-family:{FONT}; max-width:900px;
        margin:2rem auto; padding:0 1rem; line-height:1.5; }}
 a {{ color:#2a78d6; }} h1 {{ font-size:1.4rem; }}
 table {{ border-collapse:collapse; background:{SURFACE}; width:100%; }}
 th,td {{ border:1px solid {GRID}; padding:.4rem .6rem; text-align:left;
          font-variant-numeric: tabular-nums; }}
 th {{ color:{INK2}; }} .muted {{ color:{MUTED}; font-size:.9rem; }}
</style></head><body>
<h1>Predicted complexity vs observed effort (v0)</h1>
<p>49 fork–EIP relationships, five forks. Predicted scores: Task 05 isolated
historical assessments. Observed metrics: Task 07 <code>observed-metrics-v0</code>,
defined and computed score-blind before this join. Open markers = Amsterdam
(right-censored, potentially in-sample). Dashed rules mark the Low/Medium/High
tier boundaries (12, 23).</p>
<p>{legend}</p>
<p><a href="dashboard.html"><strong>Dashboard — all panels</strong></a> ·
<a href="fork-totals.html">Total predicted complexity per fork</a> ·
<a href="fork-shipping.html">Fork ship time vs complexity</a> ·
<a href="table.html">Full data table</a> ·
<a href="predicted-vs-observed.csv">joined CSV</a> ·
<a href="rank-correlations.csv">correlations CSV</a> ·
<a href="redundancy-report.md">metric-selection report</a></p>
<table>
<tr><th>Metric (click for chart)</th><th>n</th><th>Spearman ρ</th><th>p</th>
<th>Kendall τ</th><th>within-fork ρ̄</th></tr>
{rows}
</table>
<p class="muted">Generated by research/tasks/07-observed-effort-metrics/scripts/plot_predicted_vs_observed.py
(calculation observed-metrics-v0). Individual charts have click-to-highlight
legends and per-point tooltips.</p>
</body></html>"""
    (JOIN / "index.html").write_text(html)


def write_table(df: pd.DataFrame) -> None:
    cols = ["fork", "eip", "eip_title", "predicted_score", "predicted_tier",
            "days_cutoff_to_mainnet", "subst_revisions_after_cutoff",
            "devnet_count", "deps_final", "deps_after_cutoff",
            "observed_effort_composite_v0", "cohort", "censored"]
    body = df[cols].sort_values(["fork", "predicted_score"],
                                ascending=[True, False]).to_html(
        index=False, float_format=lambda v: f"{v:.2f}", border=0, na_rep="")
    fork_options = "".join(f"<option value='{f}'>{FORK_LABELS[f]}</option>"
                           for f in FORKS)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Joined data — predicted vs observed</title>
<style>
 body {{ background:{PAGE}; color:{INK}; font-family:{FONT}; margin:2rem; }}
 table {{ border-collapse:collapse; background:{SURFACE}; }}
 th,td {{ border:1px solid {GRID}; padding:.3rem .55rem; text-align:right;
          font-variant-numeric: tabular-nums; }}
 td:first-child,th:first-child,td:nth-child(3),th:nth-child(3)
   {{ text-align:left; }}
 th {{ color:{INK2}; position:sticky; top:0; background:{SURFACE};
      cursor:pointer; user-select:none; white-space:nowrap; }}
 th:hover {{ background:{GRID}; }}
 th .arrow {{ color:{MUTED}; font-size:.75em; }}
 tbody tr:hover {{ background:#f4f3ef; }}
 .controls {{ margin:.8rem 0; display:flex; gap:.8rem; align-items:center;
              flex-wrap:wrap; }}
 .controls input,.controls select {{ font:inherit; padding:.3rem .5rem;
     border:1px solid {BASELINE}; border-radius:4px; background:{SURFACE};
     color:{INK}; }}
 .muted {{ color:{MUTED}; font-size:.9rem; }}
</style></head><body>
<p><a href="index.html">&larr; back</a></p>
<div class="controls">
 <input id="q" type="search" placeholder="Filter rows (any column)…" size="30">
 <select id="forkSel"><option value="">All forks</option>{fork_options}</select>
 <span id="count" class="muted"></span>
 <span class="muted">Click a column header to sort; click again to reverse.
 Empty cells (censored/missing) always sort last.</span>
</div>
{body}
<script>
(function () {{
  const table = document.querySelector("table");
  const tbody = table.tBodies[0];
  const ths = Array.from(table.tHead.rows[0].cells);
  const q = document.getElementById("q");
  const forkSel = document.getElementById("forkSel");
  const count = document.getElementById("count");
  let sortCol = -1, dir = 1;

  ths.forEach((th, i) => {{
    const arrow = document.createElement("span");
    arrow.className = "arrow";
    th.appendChild(arrow);
    th.addEventListener("click", () => {{
      dir = (sortCol === i) ? -dir : 1;
      sortCol = i;
      ths.forEach(t => t.querySelector(".arrow").textContent = "");
      arrow.textContent = dir === 1 ? " \\u25B2" : " \\u25BC";
      sortRows();
    }});
  }});

  function cellText(row, i) {{ return row.cells[i].textContent.trim(); }}

  function sortRows() {{
    const rows = Array.from(tbody.rows);
    rows.sort((a, b) => {{
      const va = cellText(a, sortCol), vb = cellText(b, sortCol);
      if (va === "" && vb === "") return 0;
      if (va === "") return 1;               // empties last either direction
      if (vb === "") return -1;
      const na = parseFloat(va), nb = parseFloat(vb);
      if (!isNaN(na) && !isNaN(nb)) return (na - nb) * dir;
      return va.localeCompare(vb) * dir;
    }});
    rows.forEach(r => tbody.appendChild(r));
  }}

  function applyFilter() {{
    const needle = q.value.trim().toLowerCase();
    const fork = forkSel.value;
    let shown = 0;
    Array.from(tbody.rows).forEach(row => {{
      const matchesFork = !fork || cellText(row, 0) === fork;
      const matchesText = !needle ||
        row.textContent.toLowerCase().includes(needle);
      const show = matchesFork && matchesText;
      row.style.display = show ? "" : "none";
      if (show) shown++;
    }});
    count.textContent = shown + " / " + tbody.rows.length + " rows";
  }}

  q.addEventListener("input", applyFilter);
  forkSel.addEventListener("change", applyFilter);
  applyFilter();
}})();
</script>
</body></html>"""
    (JOIN / "table.html").write_text(html)


def main() -> None:
    allow_partial = "--allow-partial" in sys.argv
    pred = load_predictions()
    if len(pred) != EXPECTED_ROWS and not allow_partial:
        raise SystemExit(
            f"Only {len(pred)}/{EXPECTED_ROWS} assessments present; the join is "
            "gated until all originals exist (--allow-partial for a throwaway "
            "preview).")

    observed = pd.read_csv(OUT / "observed-metrics.csv")
    composite = pd.read_csv(OUT / "observed-effort-composite-v0.csv")
    df = observed.merge(
        composite[["fork", "eip", "observed_effort_composite_v0"]],
        on=["fork", "eip"], validate="one_to_one",
    ).merge(pred, on=["fork", "eip"], how="inner", validate="one_to_one")

    JOIN.mkdir(parents=True, exist_ok=True)
    df.to_csv(JOIN / "predicted-vs-observed.csv", index=False)
    corr = correlations(df)
    corr.to_csv(JOIN / "rank-correlations.csv", index=False)

    panels_solo, panels_grid = [], []
    for (col, name, explainer) in PANELS:
        srow = corr[corr.metric == col].iloc[0].to_dict()
        panels_solo.append((col, make_panel(df, col, name, explainer, srow,
                                            interactive_legend=True)))
        panels_grid.append(make_panel(df, col, name, explainer, srow,
                                      interactive_legend=False))

    for col, chart in panels_solo:
        base_config(chart).save(JOIN / f"metric-{col}.html", inline=True)

    fork_totals = make_fork_totals(df)
    base_config(fork_totals).save(JOIN / "fork-totals.html", inline=True)
    fork_shipping = make_fork_shipping(df)
    base_config(fork_shipping).save(JOIN / "fork-shipping.html", inline=True)

    scatter_grid = alt.vconcat(
        alt.hconcat(panels_grid[0], panels_grid[1]),
        alt.hconcat(panels_grid[2], panels_grid[3]),
        alt.hconcat(panels_grid[4], panels_grid[5]),
    ).resolve_scale(color="shared", shape="shared")
    grid = alt.vconcat(
        scatter_grid, fork_totals, make_fork_shipping(df),
        title=alt.TitleParams(
            text="Predicted complexity vs observed-effort metrics (v0)",
            subtitle=["One point per fork–EIP relationship. Open markers = "
                      "Amsterdam (right-censored, potentially in-sample). "
                      "Dashed rules: tier boundaries (Medium ≥ 12, High ≥ 23)."],
            fontSize=16, subtitleFontSize=12, anchor="start"),
    ).resolve_scale(color="independent", shape="independent")
    dashboard = base_config(grid)
    dashboard.save(JOIN / "dashboard.html", inline=True)
    dashboard.save(JOIN / "dashboard.png", scale_factor=2)

    shutil.copy(OUT / "redundancy" / "redundancy-report.md",
                JOIN / "redundancy-report.md")
    write_table(df)
    write_index(corr)

    print(corr.drop(columns=["label"]).to_string(index=False))
    print(f"\n{len(df)} joined rows -> {JOIN}")


if __name__ == "__main__":
    main()
