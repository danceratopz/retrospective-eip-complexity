# Task 04 outputs

Fork-specific EIP ref proposals live under `fork-eips/<fork-id>/`. Human-review timelines generated from those proposals live under `review/<fork-id>/`.

`anchor-fallback-policy.yaml` freezes the proposal-anchor precedence and the evidence boundary used for proposal generation. It requires explicit PFI first, then a precisely defined Task 01 historical proposal equivalent, and keeps ambiguous cases review-gated. It also prohibits Task 02 client histories, every Task 05 input or output, and observed implementation or test-network outcomes.

The review timeline reuses the locked Task 03 renderer. Each EIP panel has fixed event lanes, from top to bottom: the selected historical revision as a large magenta `REF` flag, followed by labelled `PFI`, `CFI`, and `SFI` flags, then relevant devnet/testnet markers at the bottom. The selected ref retains a solid magenta rule, and the proposal anchor is an amber dashed rule. Review status remains available in each assessment marker's tooltip.

A CFI event inherited from a Rollup Improvement Proposal precursor is labelled `CFI (RIP)`; its tooltip retains the precursor's complete identifier and provenance.

Run from the repository root:

```bash
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04-complexity-assessment-ref-selection/scripts/render_review.py --validate-only --fork osaka
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04-complexity-assessment-ref-selection/scripts/render_review.py --fork osaka
```

Validate Task 04 inventories, anchor-policy precedence, UTC brackets, selected commits, blob/content hashes, review gates, and cross-fork reuse without reading later-task material:

```bash
uv run --project research/tasks/03-fork-development-timelines --locked python research/tasks/04-complexity-assessment-ref-selection/scripts/validate_outputs.py
```

Do not hand-edit `plot-data.json`, Vega-Lite JSON, manifests, HTML, SVG, or PDF.

One proposed complexity-assessment EIP ref is written per fork–EIP relationship under `fork-eips/<fork-id>/`. Records remain proposals until their `review.status` is changed to `approved` by a separate review step.

Do not hand-edit agent-owned outputs while a fork run is active.
