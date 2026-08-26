# Task 07: Observed-effort metrics (Tier 1)

## Objective

Compute candidate observed-effort metrics for every execution-affecting fork–EIP relationship, using only canonical records already gathered by Tasks 01, 03, 04, and 04b. These metrics will later be compared with the Task 05 predicted complexity scores to evaluate whether the rubric predicts observed development experience.

This task derives metrics. It does not read, join, or correlate against any Task 05 assessment output. Keeping metric definition and redundancy analysis blind to the predicted scores prevents the observed-outcome definitions from being fitted to the predictions. The prediction–outcome join happens in a later analysis step, only after all 49 original assessments exist and the primary dataset is frozen.

## Unit of analysis

One fork–EIP relationship (49 rows). Each row is parameterized by its fork context (mainnet activation, devnet series, fork cutoff) but the row is the EIP. Fork-level aggregates are a later, explicitly illustrative view (five data points).

## Inputs

- `research/tasks/04-complexity-assessment-ref-selection/outputs/fork-eips/<fork>/eip-<n>.yaml` — the human-approved `selection.information_cutoff_at` is the authoritative start of each row's observation window. Only records with `review.status: approved` are eligible.
- `research/tasks/01-fork-eip-history/outputs/eips/eip-<n>.yaml` — revision and dependency histories.
- `research/tasks/01-fork-eip-history/outputs/fork-eips/<fork>/eip-<n>.yaml` — normalized inclusion-state events.
- `research/tasks/03-fork-development-timelines/inputs/forks/<fork>.yaml` — fork milestones (mainnet) and devnets with per-EIP participation.
- `research/tasks/04b-fork-evaluation-cutoffs/outputs/forks/<fork>.yaml` — cohort and late-scope labels. These remain **provisional** until Task 04b passes human review; rows carry the labels but no metric depends on them.

## Observation window

- `window_start` = `information_cutoff_at`, normalized to 00:00:00Z when day-precision.
- `window_end` = fork mainnet activation; for a fork not yet activated (Amsterdam), the censor date `2026-08-25T00:00:00Z`, with `censored: true` on every row of that fork.
- Devnet participation is **not** filtered by `window_start`: feature-series devnets can predate the cutoff (for example the EIP-4844 devnets predate the Cancun scope decision) and are genuine integration evidence. `days_cutoff_to_first_devnet` is therefore allowed to be negative.

## Candidate metrics

| id | Formula | Interpretation | Caveat |
| --- | --- | --- | --- |
| `days_cutoff_to_mainnet` | mainnet − cutoff, days | Delivery lead time / exposure | Within a fork, mainnet is constant, so within-fork variation is entirely "how early the EIP entered scope". Null when censored. |
| `subst_revisions_after_cutoff` | count of revision events with `semantic_effect: substantive` and cutoff < `committed_at` ≤ window_end | Specification churn/rework after assessment | Author squash/split style; healthy clarification counts too. |
| `normative_revisions_after_cutoff` | subset of the above with `change_type: normative_behavior` | Hard behavioral churn | Subset of the previous metric, not independent. |
| `devnet_count` | fork-series devnets whose explicit `participation` includes the EIP | Integration iterations / exposure | Devnets add EIPs when implementations are ready and rarely drop them, so high counts also mean "ready early in a devnet-heavy fork". |
| `devnet_span_days` | last − first participating devnet | Duration in the integration loop | Entangled with `devnet_count` and entry timing. Null when no participation. |
| `days_cutoff_to_first_devnet` | first participating devnet − cutoff | Integration lag: time from entering scope to first multi-client deployment | Closest available proxy for "time to working implementation" without Task 02. Negative when feature devnets predate scope entry. Null when no participation. |
| `deps_final` | distinct `target_eip` with `relationship` ∈ {requires, interacts_with} and event `occurred_at` ≤ window_end | Coordination surface | Frontmatter dependency declarations lag design reality; `other` (analogies) excluded. |
| `deps_after_cutoff` | subset of the above first evidenced after the cutoff | Emergent coupling discovered during development | — |
| `inclusion_reversals` | count of ordered normalized-state regressions in the fork relationship | Process churn (demotions, removals) | Mostly zeros; high-signal when nonzero. |
| `days_cutoff_to_sfi` | first `scheduled_for_inclusion` event − cutoff | Decision latency (controversy/coordination) | Zero or slightly negative when the relationship enters at SFI; era vocabulary differs. Null when no SFI-equivalent event. |

Counts of events with `semantic_effect: uncertain` and inferred devnet participation are recorded in separate diagnostic fields, never merged into primary counts. Missing means unknown, never zero.

## Redundancy analysis and metric selection

The final reported set (3–6 metrics) and any composite are selected by construct, checked against data:

1. Group candidates by construct: delivery exposure, specification rework, integration, coordination.
2. Compute Spearman correlations among observed metrics only — both on raw pooled values and on within-fork percentile ranks (percentiles remove fork-era level differences).
3. Metrics that are near-deterministic functions of one another through shared mechanics are collapsed to one representative per group; correlation alone is not a deletion criterion (correlated noisy proxies of the same construct reduce noise when averaged — the danger is double-weighting a construct, not correlation per se).
4. Composite (`observed_effort_composite_v0`): equal-weight mean of the within-fork percentile ranks of one representative per construct group, computed over the groups available for that row (Amsterdam lacks delivery lead time). The number of contributing components is recorded per row. Weights are never tuned against predicted scores, and no metric is pruned for correlating (or not) with predictions.

## How to run

```bash
cd research/tasks/07-observed-effort-metrics
uv run scripts/compute_metrics.py             # writes outputs/observed-metrics.{yaml,csv} and the within-fork percentile table
uv run scripts/analyze_redundancy.py          # writes outputs/redundancy/ matrices and outputs/observed-effort-composite-v0.csv
uv run scripts/plot_predicted_vs_observed.py  # PREDICTION JOIN: gated until all 49 Task 05 outputs exist
```

All scripts are deterministic given the input records and the pinned censor date; rerunning reproduces identical outputs except the recorded `generated_at` timestamp. The first two scripts are score-blind. Only `plot_predicted_vs_observed.py` reads Task 05 outputs; it refuses a partial assessment set unless `--allow-partial` is passed for a throwaway preview.

To view the interactive charts from another machine, serve the join directory:

```bash
python3 -m http.server 8377 --bind 0.0.0.0 --directory outputs/join
# then open http://<host>:8377/
```

## Outputs

```text
outputs/
├── observed-metrics.yaml               # per-row metrics with window, rules, and contributing event/devnet/dependency IDs
├── observed-metrics.csv                # flat analysis table
├── observed-metrics-withinfork-pct.csv # within-fork percentile ranks of each metric
├── observed-effort-composite-v0.csv    # composite + leave-one-out sensitivity variants
├── redundancy/
│   ├── spearman-raw.csv                # pooled Spearman on raw values
│   ├── spearman-withinfork-pct.csv     # Spearman on within-fork percentile ranks
│   ├── non-null-counts.csv             # metric coverage
│   └── redundancy-report.md            # grouping decision and final metric selection (analysis note)
└── join/                               # prediction-outcome join (only after all 49 assessments)
    ├── predicted-vs-observed.csv       # joined analysis table
    ├── rank-correlations.csv           # Spearman/Kendall per metric, pooled and mean within-fork
    ├── index.html                      # entry page: links, palette legend, correlation summary
    ├── dashboard.html                  # all six panels, interactive (tooltips)
    ├── metric-<name>.html              # one chart per metric with click-to-highlight legend
    ├── fork-totals.html                # stacked bar: total predicted complexity per fork, split by 04b cohort
    ├── fork-shipping.html              # fork ship time (first ≥2-EL devnet → mainnet) vs summed/High-tier/max complexity (n=5, descriptive)
    ├── table.html                      # full joined table (accessibility relief view)
    ├── dashboard.png                   # raster render for quick inspection
    └── redundancy-report.md            # copy served alongside the charts
```

Fork-level development start is enshrined (decision 2026-08-26) as **the fork's first devnet running at least two independent EL implementations**, aligning with Task 02's "development underway in earnest" heuristic (second independent client). Only Cancun differs from a naive first-EL-devnet reading: its devnets 1–3 ran a single patched go-ethereum fork, so its clock starts at dencun-devnet-4 (launched with geth + nethermind; evidence: ethpandaops/dencun-devnets inventory at commit `94ae639`). See `MULTI_EL_FIRST_DEVNET` in `scripts/plot_predicted_vs_observed.py`.

`observed-metrics.yaml` carries a `calculation_version` (`observed-metrics-v0`) and per-row evidence IDs so every count can be traced back to Task 01/03 event records. The CSV files, correlation matrices, and HTML/PNG figures are derived artifacts regenerated by the scripts and must not be edited by hand. Chart design: one point per fork–EIP relationship; fork identity is encoded by a validated five-hue palette plus distinct marker shapes (colorblind secondary encoding); Amsterdam renders as open markers because it is right-censored and potentially in-sample; dashed rules mark the rubric tier boundaries (Medium ≥ 12, High ≥ 23).
