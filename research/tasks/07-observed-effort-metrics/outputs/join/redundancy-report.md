# Redundancy analysis and final metric selection (observed-metrics-v0)

Date: 2026-08-25. Basis: `outputs/observed-metrics.csv` (49 rows) and the Spearman matrices in this directory. This analysis used only observed↔observed relationships; no Task 05 predicted score was read, joined, or correlated at any point. Selection criteria are construct-based; the correlation matrices were used solely to detect mechanical redundancy, not to optimize agreement with predictions.

## Correlation evidence used

Spearman on within-fork percentile ranks (which remove fork-era level differences):

- `devnet_count` ↔ `devnet_span_days`: **0.95** — near-deterministic under the regular devnet cadence; one degree of freedom, not two.
- `subst_revisions_after_cutoff` ↔ `normative_revisions_after_cutoff`: **0.78** — subset relation by construction.
- `days_cutoff_to_first_devnet` ↔ `days_cutoff_to_mainnet`: **0.71**, and ↔ `days_cutoff_to_sfi`: **0.82** — the "integration lag" candidate is dominated by scope-entry timing and fork ramp-up (an EIP pinned early waits idle until the fork's devnet series starts), not by implementation speed. The devnet-layering signal therefore collapses into the entry-timing/exposure family rather than providing an independent effort reading.
- `deps_final` ↔ `deps_after_cutoff`: **0.64** — related level/flow pair; `deps_after_cutoff` also mechanically overlaps spec churn (dependency events are themselves EIP-source revisions).
- `days_cutoff_to_mainnet` ↔ `devnet_count`: **0.73** — both partly measure "entered early and stayed in the loop" (exposure).

## Decisions

Dropped from the reported set:

- `normative_revisions_after_cutoff` — subset of substantive churn; kept as a diagnostic column.
- `devnet_span_days` — redundant with `devnet_count` (0.95).
- `days_cutoff_to_first_devnet` — measures fork ramp-up plus entry timing, not implementation effort (see above); kept as a diagnostic column.
- `days_cutoff_to_sfi` — structurally missing for all of Shanghai (that era's process has no normalized `scheduled_for_inclusion` state) and degenerate (0 by construction) for rows whose assessment anchor is the SFI-equivalent event itself; not cross-era comparable. Diagnostic only.
- `inclusion_reversals` — zero on all 49 rows under the normalized-state definition. The one known real churn episode (Amsterdam EIP-2780's brief SFI listing, reversion to CFI, and later SFI) was normalized by Task 01 as `unknown` states and is visible in the `unknown_inclusion_events` diagnostic instead. A constant column must not enter a within-fork-percentile composite (percentiles of a constant encode fork size, a pure artifact).

## Final reported metrics (5)

| Metric | Construct | Coverage |
| --- | --- | --- |
| `days_cutoff_to_mainnet` | Delivery lead time / exposure (NOT effort; within a fork this is scope-entry earliness) | 34/49 (Amsterdam censored) |
| `subst_revisions_after_cutoff` | Specification rework | 49/49 |
| `devnet_count` | Integration exposure | 49/49 |
| `deps_final` | Coordination surface | 49/49 |
| `deps_after_cutoff` | Emergent coupling discovered after assessment | 49/49 |

## Composite

`observed_effort_composite_v0` = equal-weight mean of the within-fork percentile ranks of `subst_revisions_after_cutoff`, `devnet_count`, and `deps_final` — one representative per effort construct group (rework, integration, coordination).

- `days_cutoff_to_mainnet` is deliberately excluded: it is a delivery/scheduling measure, mixes exposure with effort, and is censored for Amsterdam. It is reported alongside, never inside, the composite.
- `deps_after_cutoff` is reported but excluded from the composite to avoid double-counting: its underlying events are a subset of the spec-churn revisions.
- Leave-one-out variants (`composite_without_*`) are emitted for sensitivity; conclusions that do not survive all three variants should not be attributed to the composite.
- Percentile ranks are computed within fork, so the composite expresses "observed effort relative to the EIP's own fork" and is comparable across eras only in that relative sense.

Face validity (computed blind to predictions): the top composite rows are Cancun 4844, Shanghai 4895, Amsterdam 7928, Amsterdam 8037, Osaka 7918; the bottom rows are Prague 7642, Prague 7840, Osaka 7935, Amsterdam 8246, Shanghai 6049.

## Known measurement limitations

- Devnet participation is recorded from explicit protocol configuration; networking/RPC-level EIPs (7642 eth/69, 7910 `eth_config`) legitimately show `devnet_count` 0 even where devnets exercised them. Their integration signal is under-measured.
- `deps_*` counts come from EIP-source dependency events (`requires`/`interacts_with`); design-level coupling never reflected in EIP frontmatter or text is invisible.
- Amsterdam rows are right-censored on every windowed metric (window ends at the 2026-08-25 censor date, not mainnet) and the fork is potentially in-sample for the rubric; treat separately in all analyses.
- Spec churn counts inherit author squash/split style and count healthy clarification alongside rework; the `change_type` vector in the YAML output allows later reweighting without recomputation.
